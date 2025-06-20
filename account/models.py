from django.contrib.auth.models import User
from django.db import models


class Member(models.Model):
    EXPERIMENT_GROUP_LONG = 'long'
    EXPERIMENT_GROUP_SHORT = 'short'
    EXPERIMENT_GROUP_OPTIONS = (
        (EXPERIMENT_GROUP_LONG, 'Long'),
        (EXPERIMENT_GROUP_SHORT, 'Short'),
    )

    ROLE_MEMBER = 'member'
    ROLE_STAFF = 'staff'
    ROLE_OPTIONS = (
        (ROLE_MEMBER, 'Member'),
        (ROLE_STAFF, 'Staff'),
    )

    user = models.OneToOneField(User, related_name='member', on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    experiment_group = models.CharField(
        max_length=50, choices=EXPERIMENT_GROUP_OPTIONS, null=True
    )
    role = models.CharField(max_length=50, choices=ROLE_OPTIONS, default=ROLE_MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user_id}/{self.user.email}/{self.experiment_group}"
