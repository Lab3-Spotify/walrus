from abc import ABC, abstractmethod

from django.utils import timezone

from provider.caches import MemberAPITokenCache
from provider.exceptions import ProviderException
from provider.models import MemberAPIToken
from utils.constants import ResponseCode, ResponseMessage


class BaseAuthProviderHandler(ABC):
    def __init__(self, provider):
        self.provider = provider

    @property
    @abstractmethod
    def auth_interface(self):
        pass

    def extract_token_fields(self, token_data):
        return {
            'member_id': token_data.get('member_id'),
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'expires_in': token_data.get('expires_in'),
            'expires_at': token_data.get('expires_at'),
        }

    def process_token(self, request, token_data):
        token_fields = self.extract_token_fields(token_data)
        expires_in, expires_at = self._resolve_expiration_fields(
            token_fields.get('expires_in'), token_fields.get('expires_at')
        )

        api_token, _ = MemberAPIToken.objects.update_or_create(
            member_id=token_fields.get('member_id'),
            provider=self.provider,
            defaults={
                'access_token': token_fields.get('access_token'),
                'refresh_token': token_fields.get('refresh_token'),
                'expires_at': expires_at,
            },
        )
        MemberAPITokenCache.set_token(
            member_id=token_fields.get('member_id'),
            provider_code=self.provider.code,
            token=token_fields.get('access_token', ''),
            timeout=expires_in,
        )

        return {
            'member': api_token.member_id,
            'provider': self.provider.code,
            'access_token': api_token.access_token,
        }

    def _calculate_expires_at(self, expires_in):
        return timezone.now() + timezone.timedelta(seconds=expires_in)

    def _resolve_expiration_fields(self, expires_in, expires_at):
        if expires_at and not expires_in:
            if isinstance(expires_at, str):
                from django.utils.dateparse import parse_datetime

                expires_at_dt = parse_datetime(expires_at)
            else:
                expires_at_dt = expires_at
            expires_in = int((expires_at_dt - timezone.now()).total_seconds())
        elif expires_in and not expires_at:
            expires_at = self._calculate_expires_at(expires_in)
        elif not expires_in and not expires_at:
            expires_in = (
                getattr(self.provider, 'default_token_expiration', None) or 3600
            )
            expires_at = self._calculate_expires_at(expires_in)
        return expires_in, expires_at


class BaseAPIProviderHandler(ABC):
    def __init__(self, provider, member=None):
        self.provider = provider
        self.member = member

    @property
    @abstractmethod
    def api_interface(self):
        pass

    def get_access_token(self):
        access_token = MemberAPITokenCache.get_token(self.member.id, self.provider.code)
        if access_token:
            return access_token
        access_token = self.refresh_token()
        if not access_token:
            raise ProviderException(
                code=ResponseCode.EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND,
                message=ResponseMessage.EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND,
            )
        return access_token

    @abstractmethod
    def refresh_token(self):
        raise NotImplementedError('Subclasses must implement refresh_token')
