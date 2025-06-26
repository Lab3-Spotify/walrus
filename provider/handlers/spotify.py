from functools import cached_property

from django.urls import reverse

from provider.handlers.base import BaseProviderHandler
from provider.interfaces.spotify import SpotifyAuthInterface
from walrus import settings


class SpotifyAuthHandler(BaseProviderHandler):
    @cached_property
    def auth_interface(self):
        return SpotifyAuthInterface(
            auth_type=self.provider.auth_type,
            auth_details=self.provider.auth_details,
            client_id=settings.SPOTIFY_CLIENT_ID,
            client_secret=settings.SPOTIFY_CLIENT_SECRET,
        )

    def get_authorize_url(self, request):
        redirect_uri = self._get_redirect_uri(request)
        return self.auth_interface.get_authorize_url(
            redirect_uri=redirect_uri,
            scope=self._format_auth_scope(
                self.provider.extra_details.get('auth_scope', [])
            ),
            state=request.user.member.id,
        )

    def handle_authorize_callback(self, request):
        redirect_uri = self._get_redirect_uri(request)
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

    def _get_redirect_uri(self, request):
        if settings.ENV == 'local':
            return 'http://127.0.0.1:8000/callback'
        else:
            return request.build_absolute_uri(
                reverse('provider:spotify_auth-authorize_callback')
            )

    def _format_auth_scope(self, scope):
        return ' '.join(scope)
