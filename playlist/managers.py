from django.db import models


class PlaylistManager(models.Manager):
    """Playlist Manager"""

    def get_or_create_for_member(
        self, member, playlist_type, spotify_playlist_id, description
    ):
        """
        獲取或創建指定類型的歌單

        :param member: Member instance
        :param playlist_type: Playlist.TypeOptions
        :param spotify_playlist_id: Spotify playlist ID
        :param description: 歌單描述
        :return: (Playlist, created)
        """
        playlist, created = self.get_or_create(
            member=member,
            type=playlist_type,
            defaults={
                'external_id': spotify_playlist_id,
                'description': description,
            },
        )

        if not created:
            # 更新 external_id 和 description
            playlist.external_id = spotify_playlist_id
            playlist.description = description
            playlist.save()

        return playlist, created


class PlaylistTrackManager(models.Manager):
    """PlaylistTrack Manager"""

    pass
