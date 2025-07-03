from provider.models import Provider
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        spotify_data = {
            'code': Provider.PROVIDER_CODE_SPOTIFY,
            'category': Provider.PROVIDER_CATEGORY_MUSIC,
            'base_url': 'https://api.spotify.com/v1/',
            'auth_type': Provider.PROVIDER_AUTH_TYPE_OAUTH2,
            'auth_details': {
                'token_header': 'Authorization',
                'token_prefix': 'Basic',
                'use_basic_auth': True,
            },
            'extra_details': {
                'auth_scope': [
                    'user-read-private',
                    'user-read-email',
                    'user-library-read',
                    'user-read-recently-played',
                    'playlist-read-private',
                    'user-follow-read',
                    'playlist-read-private',
                    'user-top-read',
                ]
            },
            'api_handler': 'provider.handlers.spotify.SpotifyAPIProviderHandler',
            'auth_handler': 'provider.handlers.spotify.SpotifyAuthProviderHandler',
            'display_name': 'Spotify',
            'description': 'Spotify 音樂串流服務 OAuth2 Provider',
            'default_token_expiration': 3600,
        }
        Provider.objects.update_or_create(
            code=spotify_data['code'], defaults=spotify_data
        )
