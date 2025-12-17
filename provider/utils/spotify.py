"""
Spotify 資料轉換工具

純函數：將 Spotify API 原始資料轉換為標準化的 dataclass
"""
import logging
from typing import List

from django.utils import timezone

from listening_profile.schemas import PlayLogSchemas
from track.schemas import ArtistSchemas, TrackSchemas

logger = logging.getLogger(__name__)


# ===== Artist 相關 =====


def parse_artist(raw: dict) -> ArtistSchemas.CreateData:
    """
    將 Spotify API artist 轉換為標準格式

    Spotify API 文檔: https://developer.spotify.com/documentation/web-api/reference/get-an-artist

    所需字段:
    - id (str, required): Artist ID
    - name (str, required): Artist name
    - popularity (int, optional): 0-100
    - followers.total (int, optional): Follower count

    :param raw: Spotify API 返回的 artist 對象
    :return: ArtistSchemas.CreateData
    :raises ValueError: 如果缺少必填字段
    """
    if not raw.get('id'):
        raise ValueError(f"Artist missing 'id': {raw}")

    return ArtistSchemas.CreateData(
        external_id=raw['id'],
        name=raw.get('name', '')[:200],  # 防止超長
        popularity=raw.get('popularity'),
        followers_count=raw.get('followers', {}).get('total'),
    )


def parse_artists(raw_list: List[dict]) -> List[ArtistSchemas.CreateData]:
    """
    批量轉換 artists

    :param raw_list: Spotify API 返回的 artist 列表
    :return: List[ArtistSchemas.CreateData]
    """
    artists_data = []
    for raw in raw_list:
        try:
            artists_data.append(parse_artist(raw))
        except ValueError as e:
            logger.warning(f"Skipping invalid artist: {e}")
            continue

    return artists_data


def parse_artists_from_tracks(tracks_raw: List[dict]) -> List[ArtistSchemas.CreateData]:
    """
    從 tracks 資料中提取並轉換 artists

    所需字段:
    - artists (List[dict], required): Artist 列表

    :param tracks_raw: Spotify API 返回的 track 列表
    :return: List[ArtistSchemas.CreateData] (去重後)
    """
    # 收集所有 artist，使用 dict 自動去重
    all_artists = {}
    for track in tracks_raw:
        for artist in track.get('artists', []):
            artist_id = artist.get('id')
            if artist_id and artist_id not in all_artists:
                all_artists[artist_id] = artist

    return parse_artists(list(all_artists.values()))


# ===== Track 相關 =====


def parse_track(raw: dict) -> TrackSchemas.CreateData:
    """
    將 Spotify API track 轉換為標準格式

    Spotify API 文檔: https://developer.spotify.com/documentation/web-api/reference/get-track

    所需字段:
    - id (str, required): Track ID
    - name (str, required): Track name
    - artists (List[dict], required): Artist 列表 [{'id': str, 'name': str}]
    - popularity (int, optional): 0-100
    - is_playable (bool, optional): 是否可播放
    - external_ids.isrc (str, optional): ISRC code

    :param raw: Spotify API 返回的 track 對象
    :return: TrackSchemas.CreateData
    :raises ValueError: 如果缺少必填字段
    """
    if not raw.get('id'):
        raise ValueError(f"Track missing 'id': {raw}")

    # 提取 artist IDs
    artist_ids = [artist['id'] for artist in raw.get('artists', []) if artist.get('id')]

    return TrackSchemas.CreateData(
        external_id=raw['id'],
        name=raw.get('name', '')[:200],
        artist_external_ids=artist_ids,
        popularity=raw.get('popularity'),
        is_playable=raw.get('is_playable', True),
        isrc=raw.get('external_ids', {}).get('isrc', '')[:30]
        if raw.get('external_ids', {}).get('isrc')
        else None,
    )


def parse_tracks(raw_list: List[dict]) -> List[TrackSchemas.CreateData]:
    """
    批量轉換 tracks

    :param raw_list: Spotify API 返回的 track 列表
    :return: List[TrackSchemas.CreateData]
    """
    tracks_data = []
    for raw in raw_list:
        try:
            tracks_data.append(parse_track(raw))
        except ValueError as e:
            logger.warning(f"Skipping invalid track: {e}")
            continue

    return tracks_data


# ===== PlayLog 相關 =====


def parse_playlog(raw: dict) -> PlayLogSchemas.CreateData:
    """
    將 Spotify API recently played item 轉換為標準格式

    Spotify API 文檔: https://developer.spotify.com/documentation/web-api/reference/get-recently-played

    所需字段:
    - track.id (str, required): Track ID
    - played_at (str, required): ISO 8601 datetime
    - context.type (str, optional): 'playlist', 'album', 'artist'
    - context.uri (str, optional): Spotify URI (需要提取 ID)

    :param raw: Spotify API 返回的 recently played item
        {
            'track': {'id': str, ...},
            'played_at': '2024-11-08T12:34:56.789Z',
            'context': {'type': 'playlist', 'uri': 'spotify:playlist:xxxxx'}
        }
    :return: PlayLogSchemas.CreateData
    :raises ValueError: 如果缺少必填字段
    """
    track = raw.get('track', {})
    if not track.get('id'):
        raise ValueError(f"PlayLog missing 'track.id': {raw}")

    played_at_str = raw.get('played_at')
    if not played_at_str:
        raise ValueError(f"PlayLog missing 'played_at': {raw}")

    # 解析 played_at（使用 Django 的 parse_datetime 自動處理時區）
    from django.utils.dateparse import parse_datetime

    played_at = parse_datetime(played_at_str)
    if not played_at:
        raise ValueError(f"Invalid played_at format '{played_at_str}'")

    # 解析 context（可選）
    context = raw.get('context')
    context_type = None
    context_external_id = None

    if context:
        context_type = context.get('type')
        uri = context.get('uri', '')
        # 從 URI 提取 ID: "spotify:playlist:xxxxx" -> "xxxxx"
        if uri:
            parts = uri.split(':')
            if len(parts) >= 3:
                context_external_id = parts[2]

    return PlayLogSchemas.CreateData(
        track_external_id=track['id'],
        played_at=played_at,
        context_type=context_type,
        context_external_id=context_external_id,
    )


def parse_playlogs(raw_list: List[dict]) -> List[PlayLogSchemas.CreateData]:
    """
    批量轉換 recently played items

    :param raw_list: Spotify API 返回的 recently played items
    :return: List[PlayLogSchemas.CreateData]
    """
    playlogs_data = []
    for raw in raw_list:
        try:
            playlogs_data.append(parse_playlog(raw))
        except ValueError as e:
            logger.warning(f"Skipping invalid playlog: {e}")
            continue

    return playlogs_data


# ===== 去重和驗證 =====


def deduplicate_playlogs(
    playlogs_data: List[PlayLogSchemas.CreateData],
) -> List[PlayLogSchemas.CreateData]:
    """
    去重播放記錄（基於 track_external_id + played_at）

    :param playlogs_data: PlayLog 資料列表
    :return: 去重後的列表
    """
    seen_keys = set()
    deduplicated = []

    for playlog in playlogs_data:
        key = (playlog.track_external_id, playlog.played_at)
        if key not in seen_keys:
            seen_keys.add(key)
            deduplicated.append(playlog)

    return deduplicated


# ===== Pagination Helper =====


class SpotifyPaginationHelper:
    """處理 Spotify API pagination 的通用工具類"""

    API_LIMIT = 50  # Spotify API 的預設請求限制

    @staticmethod
    def fetch_all_items(api_method, total_limit=None, start_offset=0, **kwargs):
        """
        通用的 pagination 處理方法

        :param api_method: API 方法 (例如: api_interface.get_playlist_tracks)
        :param total_limit: 總共需要的資料筆數，None 表示獲取所有資料
        :param start_offset: 起始 offset（預設 0）
        :param kwargs: 傳給 API 方法的其他參數
        :return: 所有收集到的 items
        """
        all_items = []
        offset = start_offset

        while True:
            # 計算這次應該請求多少筆
            if total_limit is not None:
                remaining = total_limit - len(all_items)
                if remaining <= 0:
                    break
                current_limit = min(SpotifyPaginationHelper.API_LIMIT, remaining)
            else:
                current_limit = SpotifyPaginationHelper.API_LIMIT

            data = api_method(limit=current_limit, offset=offset, **kwargs)
            items = data.get('items', [])

            if not items:
                break

            all_items.extend(items)
            offset += len(items)

            # 如果返回的數量少於請求的 limit，表示已經沒有更多了
            if len(items) < current_limit:
                break

        return all_items
