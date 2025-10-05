import logging
from functools import cached_property
from typing import Literal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from listening_profile.models import TrackHistoryPlayLog
from provider.caches import ProviderProxyAccountAPITokenCache
from provider.decorators import member_only, proxy_account_only
from provider.handlers.base import BaseAPIProviderHandler, BaseAuthProviderHandler
from provider.interfaces.spotify import (
    SpotifyAPIProviderInterface,
    SpotifyAuthProviderInterface,
)
from provider.models import MemberAPIToken, ProviderProxyAccountAPIToken
from provider.serializers import TrackHistoryPlayLogSimpleSerializer
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
        artists_to_create, tracks_to_create = utils.prepare_entities_for_creation(
            valid_items
        )
        (
            created_logs,
            new_artist_external_ids,
        ) = utils.bulk_create_and_associate_entities(
            artists_to_create, tracks_to_create, valid_items
        )

        if new_artist_external_ids:
            from provider.tasks import update_artists_details

            update_artists_details.delay(
                new_artist_external_ids, self.provider.id, self.member.id
            )

        return created_logs

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
