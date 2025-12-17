from django import db
from django.db import models, transaction
from django.db.models.functions import TruncMinute

from account.models import Member
from playlist.managers import PlaylistManager, PlaylistTrackManager
from track.models import Track


class Playlist(models.Model):
    class TypeOptions(models.TextChoices):
        EXPERIMENT = ('experiment', 'Experiment')
        DISCOVER_WEEKLY = (
            'discover_weekly',
            'DIscover Weekly',
        )  # from member provided spotify id
        MEMBER_FAVORITE = (
            'member_favorite',
            'Member Favorite',
        )  # from member provided spotify id

    class LengthOptions(models.TextChoices):
        SHORT = ('short', 'Short')
        LONG = ('long', 'Long')

    class FavoriteTrackPositionOptions(models.TextChoices):
        EDGE = ('edge', 'Edge')
        MIDDLE = ('middle', 'Middle')

    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name='playlists'
    )
    # only record last external_id
    external_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    type = models.CharField(
        max_length=50,
        choices=TypeOptions.choices,
    )
    length_type = models.CharField(
        max_length=30,
        choices=LengthOptions.choices,
        null=True,
        blank=True,
        db_index=True,
    )
    favorite_track_position_type = models.CharField(
        max_length=30,
        choices=FavoriteTrackPositionOptions.choices,
        null=True,
        blank=True,
        db_index=True,
    )
    experiment_phase = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    description = models.TextField(blank=True, null=True)
    satisfaction_score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlaylistManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.type == self.TypeOptions.EXPERIMENT:
            phase_str = (
                f" Phase {self.experiment_phase}" if self.experiment_phase else ''
            )
            return f"Playlist {self.id} - {self.member.name} (實驗-{self.length_type}-{self.favorite_track_position_type}{phase_str})"
        return f"Playlist {self.id} - {self.member.name} ({self.type})"


class PlaylistTrack(models.Model):
    playlist = models.ForeignKey(
        Playlist, on_delete=models.CASCADE, related_name='playlist_tracks'
    )
    track = models.ForeignKey(
        Track, on_delete=models.CASCADE, related_name='playlist_tracks'
    )
    order = models.IntegerField()
    is_favorite = models.BooleanField(default=False)
    is_ever_listened = models.BooleanField(null=True, blank=True)
    satisfaction_score = models.IntegerField(null=True, blank=True)
    splendid_score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlaylistTrackManager()

    class Meta:
        ordering = ['playlist', '-created_at', 'order']
        unique_together = ('playlist', 'track')

    def __str__(self):
        return f"{self.playlist} - Track {self.order}: {self.track.name}"
