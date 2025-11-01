import json

from django.core.cache import cache


class SpotifyPlaylistOrderCache:
    """
    Spotify 歌單順序快取管理

    用於在 validate 和 import 之間保持資料一致性
    快取格式: spotify_playlist_order:{member_id}:{type}: [spotify_track_id1, spotify_track_id2, ...]

    快取內容說明:
    - 存儲的是 Spotify track IDs (external_id)，不是資料庫的 Track model ID
    - track_ids 順序與 Spotify API 返回的順序一致（已去重）
    - 用於確保 validate 和 import 兩個操作獲取到相同的歌曲列表
    """

    CACHE_TIMEOUT = 60 * 30  # 30 分鐘
    CACHE_KEY_PATTERN = 'spotify_playlist_order:{member_id}:{playlist_type}'

    @classmethod
    def _compose_cache_key(cls, member_id: int, playlist_type: str) -> str:
        """組成快取 key"""
        return cls.CACHE_KEY_PATTERN.format(
            member_id=member_id, playlist_type=playlist_type
        )

    @classmethod
    def set_track_ids(
        cls, member_id: int, playlist_type: str, spotify_track_ids: list[str]
    ) -> None:
        """
        設定歌單的 Spotify track IDs 快取

        Args:
            member_id: Member ID
            playlist_type: 歌單類型 (member_favorite 或 discover_weekly)
            spotify_track_ids: Spotify track IDs (external_id) 列表（已去重且按順序）
        """
        cache_key = cls._compose_cache_key(member_id, playlist_type)
        # 使用 JSON 序列化保存 list
        cache.set(cache_key, json.dumps(spotify_track_ids), cls.CACHE_TIMEOUT)

    @classmethod
    def get_track_ids(cls, member_id: int, playlist_type: str) -> list[str] | None:
        """
        取得快取的 Spotify track IDs

        Args:
            member_id: Member ID
            playlist_type: 歌單類型

        Returns:
            list[str] | None: Spotify track IDs (external_id) 列表，如果不存在則返回 None
        """
        cache_key = cls._compose_cache_key(member_id, playlist_type)
        cached_data = cache.get(cache_key)
        if cached_data is None:
            return None
        return json.loads(cached_data)

    @classmethod
    def delete_cache(cls, member_id: int, playlist_type: str) -> None:
        """
        刪除快取

        Args:
            member_id: Member ID
            playlist_type: 歌單類型
        """
        cache_key = cls._compose_cache_key(member_id, playlist_type)
        cache.delete(cache_key)

    @classmethod
    def delete_member_all_caches(cls, member_id: int) -> None:
        """
        刪除指定 member 的所有歌單驗證快取

        Args:
            member_id: Member ID
        """
        pattern = f"spotify_playlist_order:{member_id}:*"
        keys = cache.keys(pattern)
        for key in keys:
            cache.delete(key)
