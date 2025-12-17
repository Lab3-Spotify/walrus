"""
Spotify 播放記錄服務

負責協調數據獲取、轉換、數據庫操作
"""
import logging

from django.utils import timezone

from listening_profile.models import HistoryPlayLog
from provider.utils.spotify import (
    deduplicate_playlogs,
    parse_artists_from_tracks,
    parse_playlogs,
    parse_tracks,
)
from track.models import Artist, Track

logger = logging.getLogger(__name__)


class SpotifyPlayLogService:
    """
    Spotify 播放記錄服務

    職責：
    - 協調業務流程
    - 內部管理 Handler
    - 調用 utils 轉換數據
    - 調用 manager 操作 DB

    架構：
    View → Service → Handler → Interface
    """

    def __init__(self, provider, member):
        """
        :param provider: Provider 實例
        :param member: Member 實例
        """
        self.provider = provider
        self.member = member

        from provider.handlers.spotify import SpotifyAPIProviderHandler

        self.handler = SpotifyAPIProviderHandler(provider, member=member)

    def collect_recently_played_logs(self, days: int) -> list:
        """
        收集最近播放記錄

        流程：
        1. 從 Spotify API 獲取原始數據
        2. 使用 utils 轉換為標準化數據
        3. 使用 Manager 創建 Artists/Tracks
        4. 使用 Manager 創建 PlayLogs
        5. 觸發異步任務

        :param days: 獲取最近幾天的數據
        :return: 創建的 HistoryPlayLog 對象列表
        """
        # 1. Fetch data
        logger.info(
            f"Fetching recently played for member {self.member.id}, last {days} days"
        )
        raw_items = self._fetch_all_recently_played(days)

        if not raw_items:
            logger.info(f"No recently played items found for member {self.member.id}")
            return 0

        logger.info(f"Fetched {len(raw_items)} raw items")

        # 2. Transform data
        tracks_raw = [item['track'] for item in raw_items]

        artists_data = parse_artists_from_tracks(tracks_raw)
        tracks_data = parse_tracks(tracks_raw)
        playlogs_data = parse_playlogs(raw_items)

        playlogs_data = deduplicate_playlogs(playlogs_data)

        logger.info(
            f"Parsed {len(artists_data)} artists, "
            f"{len(tracks_data)} tracks, "
            f"{len(playlogs_data)} playlogs"
        )

        # 3. Artists
        artists_map = Artist.objects.bulk_create_from_data(artists_data, self.provider)
        logger.info(f"Created/found {len(artists_map)} artists")

        # 4. Tracks
        tracks_map = Track.objects.bulk_create_from_data(
            tracks_data,
            artists_map,
            self.provider,
        )
        logger.info(f"Created/found {len(tracks_map)} tracks")

        # 5. HistoryPlayLogContexts
        from listening_profile.services import HistoryPlayLogContextService

        context_data_list = [
            {
                'type': data.context_type,
                'external_id': data.context_external_id,
            }
            for data in playlogs_data
            if data.context_type and data.context_external_id
        ]
        context_map = HistoryPlayLogContextService.bulk_get_or_create_contexts(
            context_data_list
        )
        logger.info(f"Created/found {len(context_map)} contexts")

        # 6. HistoryPlayLogs
        created_logs = HistoryPlayLog.objects.bulk_create_deduplicated(
            playlogs_data,
            tracks_map,
            context_map,
            self.member,
            self.provider,
        )
        logger.info(f"Created {len(created_logs)} new play logs")

        return created_logs

    def _fetch_all_recently_played(self, days: int) -> list:
        """
        從 Spotify API 獲取所有播放記錄（處理分頁）

        :param days: 獲取最近幾天的數據
        :return: Spotify API 返回的 items 列表
        """
        now = timezone.now()
        after = int((now - timezone.timedelta(days=days)).timestamp() * 1000)

        all_items = []
        next_after = after

        while True:
            data = self.handler.fetch_recently_played_raw(after=next_after, limit=50)
            items = data.get('items', [])

            if not items:
                break

            all_items.extend(items)

            # 獲取最後一條記錄的時間戳
            last_played = items[-1]['played_at']

            # 解析時間戳
            try:
                from django.utils.dateparse import parse_datetime

                last_played_dt = parse_datetime(last_played)
                if not last_played_dt:
                    logger.warning(f"Failed to parse played_at: {last_played}")
                    break

                last_played_ts = int(last_played_dt.timestamp() * 1000)

                # 如果時間戳沒有前進，停止（防止無限循環）
                if last_played_ts <= next_after:
                    break

                next_after = last_played_ts

            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse played_at: {e}")
                break

            # 如果返回的數量少於請求的，說明沒有更多了
            if len(items) < 50:
                break

        return all_items
