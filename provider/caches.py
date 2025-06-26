from django.core.cache import cache


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
        return cache.get(cache_key)

    @classmethod
    def delete_token(cls, member_id, provider_code):
        cache_key = cls.compose_cache_key(member_id, provider_code)
        cache.delete(cache_key)

    @classmethod
    def has_token(cls, member_id, provider_code):
        cache_key = cls.compose_cache_key(member_id, provider_code)
        return cache.get(cache_key) is not None

    @classmethod
    def get_member_all_tokens(cls, member_id):
        pattern = f"member_api_token:{member_id}:*"
        keys = cache.keys(pattern)
        result = {}
        for key in keys:
            _, _, provider_code = key.split(':', 2)
            result[provider_code] = cache.get(key)
        return result

    @classmethod
    def delete_member_all_tokens(cls, member_id):
        pattern = f"member_api_token:{member_id}:*"
        keys = cache.keys(pattern)
        for key in keys:
            cache.delete(key)
