from django.core.cache import cache


class TokenBlacklistCache:
    """Token 黑名單快取管理"""

    # Token 在黑名單中的存活時間 (24小時，與 access token 過期時間一致)
    CACHE_TIMEOUT = 60 * 60 * 24
    CACHE_KEY_PATTERN = 'token_blacklist:{token_jti}'

    @classmethod
    def _compose_cache_key(cls, token_jti: str) -> str:
        """組成快取 key"""
        return cls.CACHE_KEY_PATTERN.format(token_jti=token_jti)

    @classmethod
    def add_token_to_blacklist(cls, token_jti: str) -> None:
        """
        將 token 加入黑名單

        Args:
            token_jti: JWT token 的 jti (JWT ID) claim
        """
        cache_key = cls._compose_cache_key(token_jti)
        cache.set(cache_key, True, cls.CACHE_TIMEOUT)

    @classmethod
    def is_token_blacklisted(cls, token_jti: str) -> bool:
        """
        檢查 token 是否在黑名單中

        Args:
            token_jti: JWT token 的 jti (JWT ID) claim

        Returns:
            bool: True 如果 token 在黑名單中
        """
        cache_key = cls._compose_cache_key(token_jti)
        return cache.get(cache_key, False)

    @classmethod
    def remove_token_from_blacklist(cls, token_jti: str) -> None:
        """
        從黑名單中移除 token (通常不需要，因為會自動過期)

        Args:
            token_jti: JWT token 的 jti (JWT ID) claim
        """
        cache_key = cls._compose_cache_key(token_jti)
        cache.delete(cache_key)
