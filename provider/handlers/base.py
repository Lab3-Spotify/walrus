from abc import ABC, abstractmethod

from django.utils import timezone

from provider.caches import MemberAPITokenCache, ProviderProxyAccountAPITokenCache
from provider.exceptions import ProviderException
from provider.models import MemberAPIToken, ProviderProxyAccountAPIToken
from utils.constants import ResponseCode, ResponseMessage


class BaseAuthProviderHandler(ABC):
    EXPIRE_IN_BUFFER = 60  # 1 分鐘的 buffer，確保 cache 比實際 token 更早過期

    def __init__(self, provider):
        self.provider = provider

    @property
    @abstractmethod
    def auth_interface(self):
        pass

    def extract_token_fields(self, token_data):
        return {
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'expires_in': token_data.get('expires_in'),
            'expires_at': token_data.get('expires_at'),
        }

    def process_token(self, token_data, member_id=None, proxy_account_id=None):
        """
        處理 OAuth token（member 或 proxy account 通用）

        Args:
            token_data: OAuth token data from provider
            member_id: Member ID (for member token)
            proxy_account_id: Proxy Account ID (for proxy account token)

        Returns:
            dict: Processed token information
        """
        if bool(member_id) == bool(proxy_account_id):
            raise ValueError(
                'Either member_id or proxy_account_id must be provided, but not both'
            )

        token_fields = self.extract_token_fields(token_data)
        expires_in, expires_at = self._resolve_expiration_fields(
            token_fields.get('expires_in'), token_fields.get('expires_at')
        )

        if member_id:
            return self._process_member_token(
                token_fields, expires_in, expires_at, member_id
            )
        else:
            return self._process_proxy_account_token(
                token_fields, expires_in, expires_at, proxy_account_id
            )

    def _process_member_token(self, token_fields, expires_in, expires_at, member_id):
        """內部方法：處理 member token"""
        api_token, _ = MemberAPIToken.objects.update_or_create(
            member_id=member_id,
            provider=self.provider,
            defaults={
                'access_token': token_fields.get('access_token'),
                'refresh_token': token_fields.get('refresh_token'),
                'expires_at': expires_at,
            },
        )
        # 設定 cache timeout 時減去 buffer，確保 cache 比實際 token 更早過期
        cache_timeout = max(0, expires_in - self.EXPIRE_IN_BUFFER)
        MemberAPITokenCache.set_token(
            member_id=member_id,
            provider_code=self.provider.code,
            token=token_fields.get('access_token', ''),
            timeout=cache_timeout,
        )

        return {
            'member': api_token.member_id,
            'provider': self.provider.code,
            'access_token': api_token.access_token,
        }

    def _process_proxy_account_token(
        self, token_fields, expires_in, expires_at, proxy_account_id
    ):
        """內部方法：處理 proxy account token"""
        api_token, _ = ProviderProxyAccountAPIToken.objects.update_or_create(
            proxy_account_id=proxy_account_id,
            defaults={
                'access_token': token_fields.get('access_token'),
                'refresh_token': token_fields.get('refresh_token'),
                'expires_at': expires_at,
            },
        )
        # 設定 cache timeout 時減去 buffer，確保 cache 比實際 token 更早過期
        cache_timeout = max(0, expires_in - self.EXPIRE_IN_BUFFER)
        ProviderProxyAccountAPITokenCache.set_token(
            proxy_account_code=api_token.proxy_account.code,
            provider_code=self.provider.code,
            token=token_fields.get('access_token', ''),
            timeout=cache_timeout,
        )

        return {
            'proxy_account': api_token.proxy_account.code,
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
    def __init__(self, provider, member=None, proxy_account=None):
        self.provider = provider
        self.member = member
        self.proxy_account = proxy_account

        if bool(member) == bool(proxy_account):
            raise ValueError(
                'Either member or proxy_account must be provided, but not both'
            )

    @property
    @abstractmethod
    def api_interface(self):
        pass

    def get_access_token(self):
        """
        獲取 access token，優先從 cache 獲取，如果沒有或過期則嘗試刷新
        """
        if self.member:
            access_token = MemberAPITokenCache.get_token(
                self.member.id, self.provider.code
            )
        else:  # proxy_account
            access_token = ProviderProxyAccountAPITokenCache.get_token(
                self.proxy_account.code, self.provider.code
            )

        if access_token:
            return access_token

        # Cache 中沒有有效 token，嘗試刷新
        access_token = self.refresh_token()
        if not access_token:
            account_type = 'member' if self.member else 'proxy account'
            raise ProviderException(
                code=ResponseCode.EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND,
                message=f"Unable to obtain access token for {account_type}",
            )
        return access_token

    def refresh_token(self):
        if self.member:
            return self._refresh_token_member()
        else:  # proxy_account
            return self._refresh_token_proxy_account()

    @abstractmethod
    def _refresh_token_member(self):
        raise NotImplementedError('Subclasses must implement _refresh_token_member')

    @abstractmethod
    def _refresh_token_proxy_account(self):
        raise NotImplementedError(
            'Subclasses must implement _refresh_token_proxy_account'
        )
