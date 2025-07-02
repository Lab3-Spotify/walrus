from django.db import models

from account.models import Member
from provider.models import Provider
from track.models import Genre, Track

# class TrackHistory(models.Model):
#     member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='track_histories')
#     track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='track_histories')
#     provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name='track_histories')
#     play_count = models.IntegerField(default=1)
#     last_played_at = models.DateTimeField(null=True)

#     class Meta:
#         unique_together = ('member', 'track', 'provider')

#     def __str__(self):
#         return f"{self.member} - {self.track} ({self.provider})"


class GenreHistory(models.Model):
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name='genre_histories'
    )
    genre = models.ForeignKey(
        Genre, on_delete=models.CASCADE, related_name='genre_histories'
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name='genre_histories'
    )
    count = models.IntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('member', 'genre', 'provider')

    def __str__(self):
        return f"{self.member} - {self.genre} ({self.provider}, {self.count})"


class TrackHistoryPlayLog(models.Model):
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

    class Meta:
        unique_together = ('member', 'track', 'provider', 'played_at')

    def __str__(self):
        return f"{self.member} - {self.track} ({self.provider}) @ {self.played_at}"
