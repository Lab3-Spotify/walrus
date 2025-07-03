from django.db import models

from account.models import Member
from utils.encrypt import decrypt_value, encrypt_value


class Provider(models.Model):
    PROVIDER_CODE_SPOTIFY = 'spotify'
    PROVIDER_CODE_OPTIONS = [
        (PROVIDER_CODE_SPOTIFY, 'Spotify'),
    ]

    PROVIDER_CATEGORY_MUSIC = 'music'
    PROVIDER_CATEGORY_OPTIONS = [
        (PROVIDER_CATEGORY_MUSIC, 'Music'),
    ]

    PROVIDER_AUTH_TYPE_OAUTH2 = 'oauth2'
    PROVIDER_AUTH_TYPE_JWT = 'jwt'
    PROVIDER_AUTH_TYPE_OPTIONS = [
        (PROVIDER_AUTH_TYPE_OAUTH2, 'OAuth2'),
        (PROVIDER_AUTH_TYPE_JWT, 'JWT'),
    ]

    code = models.CharField(choices=PROVIDER_CODE_OPTIONS, max_length=50, unique=True)
    category = models.CharField(choices=PROVIDER_CATEGORY_OPTIONS, max_length=100)
    auth_handler = models.CharField(
        max_length=255, unique=True, help_text='Auth Handler import path'
    )
    api_handler = models.CharField(
        max_length=255, unique=True, help_text='API Handler import path'
    )
    base_url = models.CharField(max_length=255, blank=True)
    auth_type = models.CharField(max_length=20, choices=PROVIDER_AUTH_TYPE_OPTIONS)
    auth_details = models.JSONField(null=True, default=dict)
    extra_details = models.JSONField(null=True, default=dict)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    default_token_expiration = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.category}"


class MemberAPIToken(models.Model):
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name='api_tokens'
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name='member_tokens'
    )
    _access_token = models.TextField(db_column='access_token')
    _refresh_token = models.TextField(null=True, blank=True, db_column='refresh_token')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('member', 'provider')

    def __str__(self):
        return f"{self.member} - {self.provider}"

    @property
    def access_token(self):
        return decrypt_value(self._access_token) if self._access_token else None

    @access_token.setter
    def access_token(self, value):
        self._access_token = encrypt_value(value) if value else None

    @property
    def refresh_token(self):
        return decrypt_value(self._refresh_token) if self._refresh_token else None

    @refresh_token.setter
    def refresh_token(self, value):
        self._refresh_token = encrypt_value(value) if value else None
