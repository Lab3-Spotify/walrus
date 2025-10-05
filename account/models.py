from django.contrib.auth.models import User
from django.db import models


class Member(models.Model):
    class ExperimentGroupOptions(models.TextChoices):
        LONG = ('long', 'Long')
        SHORT = ('short', 'Short')

    class RoleOptions(models.TextChoices):
        MEMBER = ('member', 'Member')
        STAFF = ('staff', 'Staff')

    user = models.OneToOneField(User, related_name='member', on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    experiment_group = models.CharField(
        max_length=50, choices=ExperimentGroupOptions.choices, null=True
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
        return f"{self.user_id}/{self.user.email}/{self.experiment_group}"
