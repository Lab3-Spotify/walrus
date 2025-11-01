from account.models import ExperimentGroup
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        # Create 4 ExperimentGroups
        groups_config = [
            {
                'code': 'SE',
                'playlist_length': ExperimentGroup.PlaylistLengthOptions.SHORT_FIRST,
                'favorite_track_position': ExperimentGroup.FavoriteTrackPositionOptions.EDGE_FIRST,
            },
            {
                'code': 'SM',
                'playlist_length': ExperimentGroup.PlaylistLengthOptions.SHORT_FIRST,
                'favorite_track_position': ExperimentGroup.FavoriteTrackPositionOptions.MIDDLE_FIRST,
            },
            {
                'code': 'LE',
                'playlist_length': ExperimentGroup.PlaylistLengthOptions.LONG_FIRST,
                'favorite_track_position': ExperimentGroup.FavoriteTrackPositionOptions.EDGE_FIRST,
            },
            {
                'code': 'LM',
                'playlist_length': ExperimentGroup.PlaylistLengthOptions.LONG_FIRST,
                'favorite_track_position': ExperimentGroup.FavoriteTrackPositionOptions.MIDDLE_FIRST,
            },
        ]

        for config in groups_config:
            ExperimentGroup.objects.get_or_create(
                code=config['code'],
                defaults={
                    'playlist_length': config['playlist_length'],
                    'favorite_track_position': config['favorite_track_position'],
                },
            )
