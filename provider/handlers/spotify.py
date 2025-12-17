import logging
from functools import cached_property
from typing import Literal

from django.urls import reverse

from provider.caches import ProviderProxyAccountAPITokenCache
from provider.decorators import member_only, proxy_account_only
from provider.handlers.base import BaseAPIProviderHandler, BaseAuthProviderHandler
from provider.interfaces.spotify import (
    SpotifyAPIProviderInterface,
    SpotifyAuthProviderInterface,
)
from provider.models import MemberAPIToken, ProviderProxyAccountAPIToken
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
        redirect_uri = self._get_redirect_url(request, account_type)
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
        redirect_uri = self._get_redirect_url(request, account_type)
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

    def _get_redirect_url(
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
                url_path = reverse('provider:spotify-auth-authorize-member-callback')
            else:  # proxy_account
                url_path = reverse(
                    'provider:spotify-auth-authorize-proxy-account-callback'
                )
            https_url = f"https://{request.get_host()}{url_path}"
            return https_url

    def _format_auth_scope(self, scope):
        return ' '.join(scope)


class SpotifyAPIProviderHandler(BaseAPIProviderHandler):
    @property
    def api_interface(self):
        """
        獲取 API Interface（唯一能創建 interface 的地方）

        自動處理 token 管理（member/proxy_account）
        """
        return SpotifyAPIProviderInterface(
            provider=self.provider,
            access_token=self.get_access_token(),
        )

    # ===== API 封裝方法（API Gateway）=====
    # Handler 是唯一能訪問 Interface 的地方
    # 使用 @member_only 防止 proxy_account 誤用

    @member_only
    def fetch_recently_played_raw(self, after=None, before=None, limit=50):
        """
        獲取播放記錄（原始數據）

        :param after: Unix timestamp (milliseconds)
        :param before: Unix timestamp (milliseconds)
        :param limit: 返回數量（max 50）
        :return: Spotify API 原始回應
        """
        return self.api_interface.get_recently_played(
            after=after, before=before, limit=limit
        )

    @member_only
    def fetch_playlist_tracks(self, playlist_id, market='TW'):
        """
        獲取歌單中的所有歌曲（自動處理分頁）

        :param playlist_id: Spotify playlist ID
        :param market: ISO 3166-1 alpha-2 country code
        :return: Track 列表（已過濾非 track 項目和不可播放的歌曲）
        """
        from provider.utils.spotify import SpotifyPaginationHelper

        items = SpotifyPaginationHelper.fetch_all_items(
            api_method=self.api_interface.get_playlist_tracks,
            total_limit=None,
            playlist_id=playlist_id,
            market=market,
        )

        tracks = [
            item['track']
            for item in items
            if item.get('track')
            and item['track'].get('type') == 'track'
            and item['track'].get('is_playable', False)  # 只取可播放的歌曲
        ]

        return tracks

    # ===== Token 刷新方法 =====

    @member_only
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

    @proxy_account_only
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
