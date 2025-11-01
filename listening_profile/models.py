from django.db import models

from account.models import Member
from provider.models import Provider
from track.models import Track


class HistoryPlayLogContext(models.Model):
    class TypeOptions(models.TextChoices):
        PLAYLIST = ('playlist', 'Playlist')
        ALBUM = ('album', 'Album')
        ARTIST = ('artist', 'Artist')

    type = models.CharField(max_length=50, choices=TypeOptions.choices)
    external_id = models.CharField(max_length=255)
    details = models.JSONField(null=True, default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('type', 'external_id')
        indexes = [
            models.Index(fields=['type', 'external_id']),
        ]

    def __str__(self):
        return f"{self.type}: {self.external_id}"


class HistoryPlayLog(models.Model):
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name='track_play_logs'
    )
    track = models.ForeignKey(
        Track, on_delete=models.CASCADE, related_name='track_play_logs'
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name='track_play_logs'
    )
    played_at = models.DateTimeField()
    context = models.ForeignKey(
        HistoryPlayLogContext,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='play_logs',
    )

    class Meta:
        unique_together = ('member', 'track', 'provider', 'played_at')

    def __str__(self):
        return f"{self.member} - {self.track} ({self.provider}) @ {self.played_at}"
