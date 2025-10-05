from provider.models import Provider
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        for i in range(2, 7):
            provider_name = f'familiarity-playlist{i}'

            if Provider.objects.filter(name=provider_name).exists():
                print(f"⚠️  Provider {provider_name} already exists, skipping...")
                continue

            spotify_data = {
                'name': provider_name,
                'code': provider_name,
                'platform': Provider.PlatformOptions.SPOTIFY,
                'category': Provider.CategoryOptions.MUSIC,
                'base_url': 'https://api.spotify.com/v1/',
                'auth_type': Provider.AuthTypeOptions.OAUTH2,
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
                        'streaming',
                        'user-modify-playback-state',
                        'user-read-playback-state',
                    ]
                },
                'api_handler': 'provider.handlers.spotify.SpotifyAPIProviderHandler',
                'auth_handler': 'provider.handlers.spotify.SpotifyAuthProviderHandler',
                'description': f'Spotify 音樂串流服務 OAuth2 Provider - {provider_name}',
                'default_token_expiration': 3600,
            }

            Provider.objects.create(**spotify_data)
            print(f"✅ Created provider: {provider_name}")

        print(
            f"🎉 Successfully created/updated {Provider.objects.filter(platform=Provider.PlatformOptions.SPOTIFY).count()} Spotify providers"
        )
