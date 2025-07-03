from django.core.cache import cache
from django.utils import timezone

from provider.models import MemberAPIToken


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
