from provider.models import Provider
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        spotify_provider = Provider.objects.get(code='familiarity-playlist1')
        scope_to_control_player = [
            'streaming',
            'user-modify-playback-state',
            'user-read-playback-state',
        ]
        spotify_provider.extra_details.get('auth_scope').extend(scope_to_control_player)
        spotify_provider.save()
