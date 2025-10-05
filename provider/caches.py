from typing import Literal

from django.core.cache import cache
from django.utils import timezone

from provider.models import MemberAPIToken, ProviderProxyAccountAPIToken


class MemberAPITokenCache:
    @staticmethod
    def compose_cache_key(member_id, provider_code):
        return f"member_api_token:{member_id}:{provider_code}"

    @classmethod
    def set_token(cls, member_id, provider_code, token, timeout):
        cache_key = cls.compose_cache_key(member_id, provider_code)
        cache.set(cache_key, token, timeout=timeout)

    @classmethod
    def get_token(cls, member_id, provider_code):
        cache_key = cls.compose_cache_key(member_id, provider_code)
        access_token = cache.get(cache_key)
        if access_token is not None:
            return access_token
        member_api_token = MemberAPIToken.objects.filter(
            member_id=member_id, provider__code=provider_code
        ).first()
        if not member_api_token or cls._is_token_expired(member_api_token.expires_at):
            return None
        access_token = member_api_token.access_token
        timeout = cls._get_token_timeout(member_api_token.expires_at)
        cls.set_token(member_id, provider_code, access_token, timeout)
        return access_token

    @classmethod
    def delete_token(cls, member_id, provider_code):
        cache_key = cls.compose_cache_key(member_id, provider_code)
        cache.delete(cache_key)

    @classmethod
    def delete_member_all_tokens(cls, member_id):
        pattern = f"member_api_token:{member_id}:*"
        keys = cache.keys(pattern)
        for key in keys:
            cache.delete(key)

    @classmethod
    def _is_token_expired(cls, expires_at):
        return expires_at and expires_at < timezone.now()

    @classmethod
    def _get_token_timeout(cls, expires_at):
        if expires_at:
            delta = (expires_at - timezone.now()).total_seconds()
            if delta <= 0:
                return 0
            return int(delta)
        return None  # None means no limit, timeout is forever


class ProviderProxyAccountAPITokenCache:
    @staticmethod
    def compose_cache_key(proxy_account_code, provider_code):
        return f"proxy_account_api_token:{proxy_account_code}:{provider_code}"

    @classmethod
    def set_token(cls, proxy_account_code, provider_code, token, timeout):
        cache_key = cls.compose_cache_key(proxy_account_code, provider_code)
        cache.set(cache_key, token, timeout=timeout)

    @classmethod
    def get_token(cls, proxy_account_code, provider_code):
        cache_key = cls.compose_cache_key(proxy_account_code, provider_code)
        access_token = cache.get(cache_key)
        if access_token is not None:
            return access_token

        proxy_account_token = ProviderProxyAccountAPIToken.objects.filter(
            proxy_account__code=proxy_account_code,
            proxy_account__provider__code=provider_code,
        ).first()

        if not proxy_account_token or cls._is_token_expired(
            proxy_account_token.expires_at
        ):
            return None

        access_token = proxy_account_token.access_token
        timeout = cls._get_token_timeout(proxy_account_token.expires_at)
        cls.set_token(proxy_account_code, provider_code, access_token, timeout)
        return access_token

    @classmethod
    def delete_token(cls, proxy_account_code, provider_code):
        cache_key = cls.compose_cache_key(proxy_account_code, provider_code)
        cache.delete(cache_key)

    @classmethod
    def delete_proxy_account_all_tokens(cls, proxy_account_code):
        pattern = f"proxy_account_api_token:{proxy_account_code}:*"
        keys = cache.keys(pattern)
        for key in keys:
            cache.delete(key)

    @classmethod
    def _is_token_expired(cls, expires_at):
        return expires_at and expires_at < timezone.now()

    @classmethod
    def _get_token_timeout(cls, expires_at):
        if expires_at:
            delta = (expires_at - timezone.now()).total_seconds()
            if delta <= 0:
                return 0
            return int(delta)
        return None  # None means no limit, timeout is forever


class MemberProviderProxyAccountCache:
    CACHE_TIMEOUT = 3600
    LOCK_TIMEOUT = 10

    @staticmethod
    def compose_cache_key(platform: str, member_id: int) -> str:
        return f"member_proxy_account:{platform}:{member_id}"

    @staticmethod
    def compose_lock_key(platform: str, member_id: int) -> str:
        """組合鎖 key"""
        return f"lock:member_proxy_account:{platform}:{member_id}"

    @classmethod
    def get_cache(cls, platform: str, member_id: int):
        """
        取得快取的 proxy account 資訊

        Args:
            platform: 平台類型
            member_id: member ID

        Returns:
            dict or None: {'proxy_account_code': str, 'provider_code': str} 或 None
        """
        cache_key = cls.compose_cache_key(platform, member_id)
        return cache.get(cache_key)

    @classmethod
    def set_cache(
        cls, platform: str, member_id: int, proxy_account_code: str, provider_code: str
    ) -> None:
        """
        設定 proxy account 資訊快取

        Args:
            platform: 平台類型
            member_id: member ID
            proxy_account_code: proxy account code
            provider_code: provider code
        """
        cache_key = cls.compose_cache_key(platform, member_id)
        cache_value = {
            'proxy_account_code': proxy_account_code,
            'provider_code': provider_code,
        }
        cache.set(cache_key, cache_value, timeout=cls.CACHE_TIMEOUT)

    @classmethod
    def delete_cache(cls, platform: str, member_id: int) -> None:
        """
        刪除快取

        Args:
            platform: 平台類型
            member_id: member ID
        """
        cache_key = cls.compose_cache_key(platform, member_id)
        cache.delete(cache_key)

    @classmethod
    def acquire_lock(cls, platform: str, member_id: int) -> bool:
        """
        嘗試獲取分散式鎖

        Args:
            platform: 平台類型
            member_id: member ID

        Returns:
            bool: True 表示成功獲取鎖，False 表示鎖已被佔用
        """
        lock_key = cls.compose_lock_key(platform, member_id)
        return cache.add(lock_key, True, timeout=cls.LOCK_TIMEOUT)

    @classmethod
    def release_lock(cls, platform: str, member_id: int) -> None:
        """
        釋放分散式鎖

        Args:
            platform: 平台類型
            member_id: member ID
        """
        lock_key = cls.compose_lock_key(platform, member_id)
        cache.delete(lock_key)
