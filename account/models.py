from django.contrib.auth.models import User
from django.db import models


class ExperimentGroup(models.Model):
    class PlaylistLengthOptions(models.TextChoices):
        SHORT_FIRST = ('short_first', 'Short First')
        LONG_FIRST = ('long_first', 'Long First')

    class FavoriteTrackPositionOptions(models.TextChoices):
        EDGE_FIRST = ('edge_first', 'Edge First')
        MIDDLE_FIRST = ('middle_first', 'Middle First')

    code = models.CharField(max_length=20, unique=True)
    playlist_length = models.CharField(
        max_length=50,
        choices=PlaylistLengthOptions.choices,
    )
    favorite_track_position = models.CharField(
        max_length=50,
        choices=FavoriteTrackPositionOptions.choices,
    )

    class Meta:
        unique_together = [('playlist_length', 'favorite_track_position')]

    def __str__(self):
        return f"{self.code}"


class Member(models.Model):
    class RoleOptions(models.TextChoices):
        MEMBER = ('member', 'Member')
        STAFF = ('staff', 'Staff')

    user = models.OneToOneField(User, related_name='member', on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    experiment_group = models.ForeignKey(
        ExperimentGroup,
        on_delete=models.PROTECT,
        related_name='members',
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=50, choices=RoleOptions.choices, default=RoleOptions.MEMBER
    )

    # Spotify一次只支援25個白名單，因此需要分配不同的spotify provider
    spotify_provider = models.ForeignKey(
        'provider.Provider',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='members',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.id}/{self.user.email}"
