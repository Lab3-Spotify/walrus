from django.db import models

from provider.models import Provider
from track.managers import ArtistManager, TrackManager


class Genre(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100, null=True, blank=True)
    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name='genres'
    )

    class Meta:
        unique_together = ('name', 'provider')

    def __str__(self):
        return f"{self.name} ({self.provider})"


class Artist(models.Model):
    external_id = models.CharField(max_length=255)
    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name='artists'
    )
    name = models.CharField(max_length=200)
    popularity = models.IntegerField(blank=True, null=True)
    followers_count = models.IntegerField(blank=True, null=True)
    genres = models.ManyToManyField(Genre, related_name='artists')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ArtistManager()

    class Meta:
        unique_together = ('external_id', 'provider')

    def __str__(self):
        return self.name


class Track(models.Model):
    external_id = models.CharField(max_length=255)
    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name='tracks'
    )
    name = models.CharField(max_length=200)
    artists = models.ManyToManyField(Artist, related_name='tracks')
    genres = models.ManyToManyField(Genre, related_name='tracks')
    popularity = models.IntegerField(blank=True, null=True)
    is_playable = models.BooleanField(default=True)
    isrc = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TrackManager()

    class Meta:
        unique_together = ('external_id', 'provider')

    def __str__(self):
        return self.name

    @property
    def clip_start_ms(self):
        """固定的 clip 開始時間（毫秒）"""
        return 0

    @property
    def clip_end_ms(self):
        """固定的 clip 結束時間（毫秒）"""
        return 45000


class TrackAudioFeatures(models.Model):
    track = models.OneToOneField(
        Track, on_delete=models.CASCADE, related_name='audio_features'
    )
    acousticness = models.FloatField(blank=True, null=True)
    danceability = models.FloatField(blank=True, null=True)
    energy = models.FloatField(blank=True, null=True)
    instrumentalness = models.FloatField(blank=True, null=True)
    liveness = models.FloatField(blank=True, null=True)
    loudness = models.FloatField(blank=True, null=True)
    speechiness = models.FloatField(blank=True, null=True)
    valence = models.FloatField(blank=True, null=True)
    tempo = models.FloatField(blank=True, null=True)
    key = models.IntegerField(blank=True, null=True)
    mode = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
