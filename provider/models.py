from django.db import models

from account.models import Member
from utils.encrypt import decrypt_value, encrypt_value


class Provider(models.Model):
    class PlatformOptions(models.TextChoices):
        SPOTIFY = ('spotify', 'Spotify')

    class CategoryOptions(models.TextChoices):
        MUSIC = ('music', 'Music')

    class AuthTypeOptions(models.TextChoices):
        OAUTH2 = ('oauth2', 'OAuth2')
        JWT = ('jwt', 'JWT')

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    platform = models.CharField(choices=PlatformOptions.choices, max_length=50)
    category = models.CharField(choices=CategoryOptions.choices, max_length=100)
    auth_handler = models.CharField(
        max_length=255, unique=False, help_text='Auth Handler import path'
    )
    api_handler = models.CharField(
        max_length=255, unique=False, help_text='API Handler import path'
    )
    base_url = models.CharField(max_length=255, blank=True)
    auth_type = models.CharField(max_length=20, choices=AuthTypeOptions.choices)
    auth_details = models.JSONField(null=True, default=dict)
    extra_details = models.JSONField(null=True, default=dict)
    description = models.TextField(blank=True)
    default_token_expiration = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.platform} - {self.category}"


class ProviderProxyAccount(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    current_member = models.ForeignKey(
        'account.Member',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='proxy_accounts',
    )

    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ('provider', 'code'),
        ]

    def __str__(self):
        return f"{self.name} - {self.provider.platform}"


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
        return f"{self.member} - {self.provider.code}"

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


class ProviderProxyAccountAPIToken(models.Model):
    proxy_account = models.OneToOneField(
        ProviderProxyAccount, on_delete=models.CASCADE, related_name='api_token'
    )
    _access_token = models.TextField(db_column='access_token')
    _refresh_token = models.TextField(null=True, blank=True, db_column='refresh_token')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.proxy_account} - Token"

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
