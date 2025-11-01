import logging
from functools import cached_property
from typing import Literal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from listening_profile.models import HistoryPlayLog
from provider.caches import ProviderProxyAccountAPITokenCache
from provider.decorators import member_only, proxy_account_only
from provider.handlers.base import BaseAPIProviderHandler, BaseAuthProviderHandler
from provider.interfaces.spotify import (
    SpotifyAPIProviderInterface,
    SpotifyAuthProviderInterface,
)
from provider.models import MemberAPIToken, ProviderProxyAccountAPIToken
from provider.serializers import HistoryPlayLogSimpleSerializer
from track.models import Artist, Track
from walrus import settings

logger = logging.getLogger(__name__)


class SpotifyAuthProviderHandler(BaseAuthProviderHandler):
    @property
    def auth_interface(self):
        return SpotifyAuthProviderInterface(
            auth_type=self.provider.auth_type,
            auth_details=self.provider.auth_details,
        )

    def get_authorize_url(
        self,
        request,
        state: int,
        account_type: Literal['member', 'proxy_account'] = 'member',
    ):
        """
        獲取授權 URL

        Args:
            request: Django request object
            state: state 參數（member_id 或 proxy_account_id）
            account_type: 'member' 或 'proxy_account'
        """
        redirect_uri = self._get_redirect_uri(request, account_type)
        return self.auth_interface.get_authorize_url(
            redirect_uri=redirect_uri,
            scope=self._format_auth_scope(
                self.provider.extra_details.get('auth_scope', [])
            ),
            state=state,
        )

    def handle_authorize_callback(
        self, request, account_type: Literal['member', 'proxy_account'] = 'member'
    ):
        """
        處理授權 callback

        Args:
            request: Django request object
            account_type: 'member' 或 'proxy_account'
        """
        redirect_uri = self._get_redirect_uri(request, account_type)
        return self.auth_interface.handle_authorize_callback(
            request, redirect_uri=redirect_uri
        )

    def extract_token_fields(self, token_data):
        return {
            'member_id': token_data.get('member_id', None),
            'access_token': token_data.get('access_token', None),
            'refresh_token': token_data.get('refresh_token', None),
            'expires_in': token_data.get('expires_in', 3600),
        }

    def _get_redirect_uri(
        self, request, account_type: Literal['member', 'proxy_account'] = 'member'
    ) -> str:
        """
        獲取 redirect URI

        Args:
            request: Django request object
            account_type: 'member' 或 'proxy_account'

        Returns:
            str: redirect URI
        """
        if settings.ENV == 'local':
            if account_type == 'member':
                return 'http://127.0.0.1:8000/callback/member/'
            else:  # proxy_account
                return 'http://127.0.0.1:8000/callback/proxy-account/'
        else:
            if account_type == 'member':
                url_path = reverse('provider:callback-member')
            else:  # proxy_account
                url_path = reverse('provider:callback-proxy-account')
            https_url = f"https://{request.get_host()}{url_path}"
            return https_url

    def _format_auth_scope(self, scope):
        return ' '.join(scope)


class SpotifyAPIProviderHandler(BaseAPIProviderHandler):
    @property
    def api_interface(self):
        return SpotifyAPIProviderInterface(
            provider=self.provider,
            access_token=self.get_access_token(),
        )

    @member_only
    def collect_recently_played_logs(self, days):
        from provider.utils.spotify_utils import SpotifyPlayLogUtils

        utils = SpotifyPlayLogUtils(self.api_interface, self.provider, self.member)

        all_items = utils.fetch_all_recently_played_items(days)
        valid_items = utils.deduplicate_and_validate_items(all_items)
        artists_to_create, tracks_to_create = utils.prepare_tracks_artists_data(
            valid_items
        )
        created_logs = utils.bulk_create_playlogs_with_relations(
            artists_to_create, tracks_to_create, valid_items
        )

        return created_logs

    @member_only
    def validate_member_playlist(self, spotify_playlist_id, playlist_type):
        """
        驗證用戶提供的 Spotify playlist 是否符合實驗要求

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型 (member_favorite 或 discover_weekly)
        :return: 驗證結果字典
        """
        from provider.utils.spotify_utils import SpotifyPlaylistValidationUtils

        validation_utils = SpotifyPlaylistValidationUtils(
            self.api_interface, self.provider, self.member
        )

        validation_result = validation_utils.validate_playlist(
            spotify_playlist_id, playlist_type
        )

        return validation_result

    @member_only
    def import_member_playlist(self, spotify_playlist_id, playlist_type):
        """
        匯入用戶提供的 Spotify playlist

        會先檢查快取的 track IDs，確保與當前從 Spotify 獲取的資料一致
        如果快取不存在或資料不一致，會拋出 ProviderException

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型 (MEMBER_FAVORITE 或 DISCOVER_WEEKLY)
        :return: Playlist object
        """
        from playlist.caches import SpotifyPlaylistOrderCache
        from provider.exceptions import ProviderException
        from provider.utils.spotify_utils import SpotifyPlaylistImportUtils
        from utils.constants import ResponseCode, ResponseMessage

        # 1. 檢查快取是否存在
        cached_track_ids = SpotifyPlaylistOrderCache.get_track_ids(
            member_id=self.member.id,
            playlist_type=playlist_type,
        )

        if cached_track_ids is None:
            raise ProviderException(
                code=ResponseCode.PLAYLIST_ORDER_CACHE_NOT_FOUND,
                message=ResponseMessage.PLAYLIST_ORDER_CACHE_NOT_FOUND,
                details={
                    'member_id': self.member.id,
                    'playlist_type': playlist_type,
                },
            )

        # 2. 使用 PlaylistImportUtils 收集歌單中的所有歌曲
        playlist_utils = SpotifyPlaylistImportUtils(
            self.api_interface, self.provider, self.member
        )
        tracks_data = playlist_utils.fetch_all_playlist_tracks(spotify_playlist_id)

        if not tracks_data:
            logger.warning(
                f"No tracks found in playlist {spotify_playlist_id} for member {self.member.id}"
            )
            return None

        # 3. 提取當前獲取的 track IDs（去除重複，使用與 validation 相同的邏輯）
        current_track_ids = playlist_utils.get_deduped_track_ids(
            tracks_data, playlist_type
        )

        # 4. 比對快取的 track IDs 與當前獲取的 track IDs
        if set(cached_track_ids) != set(current_track_ids):
            raise ProviderException(
                code=ResponseCode.PLAYLIST_ORDER_MISMATCH,
                message=ResponseMessage.PLAYLIST_ORDER_MISMATCH,
                details={
                    'cached_count': len(cached_track_ids),
                    'current_count': len(current_track_ids),
                    'cached_track_ids': cached_track_ids,
                    'current_track_ids': current_track_ids,
                },
            )

        # 5. 使用快取的順序重新排序 tracks_data
        reordered_tracks_data = playlist_utils.reorder_tracks_by_cache(
            tracks_data, cached_track_ids
        )

        # 6. 匯入或更新歌單
        playlist = playlist_utils.import_or_update_playlist(
            spotify_playlist_id, playlist_type, reordered_tracks_data
        )

        return playlist

    def _refresh_token_member(self):
        member_api_token = MemberAPIToken.objects.filter(
            member=self.member, provider=self.provider
        ).first()
        if not member_api_token or not member_api_token.refresh_token:
            return None
        auth_handler = SpotifyAuthProviderHandler(self.provider)
        refresh_result = auth_handler.auth_interface.refresh_access_token(
            member_api_token.refresh_token
        )

        # Spotify may or may not return a new refresh_token
        # If not returned, use the old one
        refresh_token = refresh_result.pop(
            'refresh_token', member_api_token.refresh_token
        )
        token_data = {
            **refresh_result,
            'refresh_token': refresh_token,
        }
        result = auth_handler.process_token(
            token_data=token_data, member_id=self.member.id
        )
        return result.get('access_token')

    def _refresh_token_proxy_account(self):
        proxy_token = ProviderProxyAccountAPIToken.objects.filter(
            proxy_account=self.proxy_account
        ).first()
        if not proxy_token or not proxy_token.refresh_token:
            return None

        auth_handler = SpotifyAuthProviderHandler(self.provider)
        refresh_result = auth_handler.auth_interface.refresh_access_token(
            proxy_token.refresh_token
        )

        # Spotify may or may not return a new refresh_token
        # If not returned, use the old one
        refresh_token = refresh_result.pop('refresh_token', proxy_token.refresh_token)
        token_data = {
            **refresh_result,
            'refresh_token': refresh_token,
        }
        result = auth_handler.process_token(
            token_data=token_data, proxy_account_id=self.proxy_account.id
        )
        return result.get('access_token')
