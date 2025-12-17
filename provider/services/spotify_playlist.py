"""
Spotify 歌單服務

負責歌單的驗證、導入等業務邏輯
"""
import logging

from django.db import transaction
from django.db.models.functions import TruncMinute
from django.utils import timezone

from playlist.models import Playlist, PlaylistTrack
from playlist.schemas import PlaylistSchemas
from provider.exceptions import ProviderException
from provider.utils.spotify import parse_artists_from_tracks, parse_tracks
from track.models import Artist, Track
from utils.constants import ResponseCode, ResponseMessage

logger = logging.getLogger(__name__)


class SpotifyPlaylistService:
    """
    Spotify 歌單服務（業務入口）

    職責：
    - 協調業務流程
    - 內部管理 Handler
    - 調用 utils 轉換數據
    - 調用 manager 操作 DB

    架構：
    View → Service (這裡) → Handler → Interface
    """

    def __init__(self, provider, member):
        """
        :param provider: Provider 實例
        :param member: Member 實例
        """
        self.provider = provider
        self.member = member

        # 內部創建 Handler（API Gateway）
        from provider.handlers.spotify import SpotifyAPIProviderHandler

        self.handler = SpotifyAPIProviderHandler(provider, member=member)

    def validate_playlist(
        self, spotify_playlist_id: str, playlist_type: str
    ) -> PlaylistSchemas.ValidationResult:
        """
        驗證 Spotify 歌單是否符合實驗要求

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型 (Playlist.TypeOptions.MEMBER_FAVORITE 或 DISCOVER_WEEKLY)
        :return: PlaylistSchemas.ValidationResult
        """
        # 1. 獲取歌單中的所有歌曲
        tracks_data = self._fetch_all_playlist_tracks(spotify_playlist_id)

        # 2. 根據類型驗證
        if playlist_type == Playlist.TypeOptions.MEMBER_FAVORITE:
            return self._validate_member_favorite_playlist(tracks_data)
        elif playlist_type == Playlist.TypeOptions.DISCOVER_WEEKLY:
            return self._validate_discover_weekly_playlist(tracks_data)
        else:
            raise ValueError(f"不支持的歌單類型: {playlist_type}")

    def import_playlist(self, spotify_playlist_id: str, playlist_type: str) -> Playlist:
        """
        導入用戶提供的 Spotify playlist

        會先檢查緩存的 track IDs，確保與當前從 Spotify 獲取的數據一致
        如果緩存不存在或數據不一致，會拋出 ProviderException

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型 (MEMBER_FAVORITE 或 DISCOVER_WEEKLY)
        :return: Playlist object
        """
        from playlist.caches import SpotifyPlaylistOrderCache

        # 1. 檢查緩存是否存在
        cached_track_ids = SpotifyPlaylistOrderCache.get_track_ids(
            member_id=self.member.id,
            playlist_type=playlist_type,
        )

        if cached_track_ids is None:
            raise ProviderException(
                code=ResponseCode.PLAYLIST_ORDER_CACHE_NOT_FOUND,
                message=ResponseMessage.PLAYLIST_ORDER_CACHE_NOT_FOUND,
                details={
                    'member_id': self.member.id,
                    'playlist_type': playlist_type,
                },
            )

        # 2. 獲取歌單中的所有歌曲
        tracks_data = self._fetch_all_playlist_tracks(spotify_playlist_id)

        if not tracks_data:
            logger.warning(
                f"No tracks found in playlist {spotify_playlist_id} for member {self.member.id}"
            )
            return None

        # 3. 提取當前獲取的 track IDs（去除重複）
        current_track_ids = self._get_deduped_track_ids(tracks_data, playlist_type)

        # 4. 比對緩存的 track IDs 與當前獲取的 track IDs
        if set(cached_track_ids) != set(current_track_ids):
            raise ProviderException(
                code=ResponseCode.PLAYLIST_ORDER_MISMATCH,
                message=ResponseMessage.PLAYLIST_ORDER_MISMATCH,
                details={
                    'cached_count': len(cached_track_ids),
                    'current_count': len(current_track_ids),
                    'cached_track_ids': cached_track_ids,
                    'current_track_ids': current_track_ids,
                },
            )

        # 5. 使用緩存的順序重新排序 tracks_data
        reordered_tracks_data = self._reorder_tracks_by_cache(
            tracks_data, cached_track_ids
        )

        # 6. 導入或更新歌單
        playlist = self._import_or_update_playlist(
            spotify_playlist_id, playlist_type, reordered_tracks_data
        )

        return playlist

    # ===== 私有方法 =====

    def _fetch_all_playlist_tracks(self, spotify_playlist_id: str) -> list:
        """
        從 Spotify API 收集歌單中的所有歌曲

        使用 market='TW' 參數讓 Spotify API 直接返回台灣市場可用的歌曲

        :param spotify_playlist_id: Spotify playlist ID
        :return: track 列表
        """
        # ✅ 通過 handler 調用 API（handler 已經處理了分頁和過濾）
        tracks = self.handler.fetch_playlist_tracks(
            playlist_id=spotify_playlist_id, market='TW'
        )

        return tracks

    def _mark_tracks_as_duplicated(
        self, tracks_data: list, current_playlist_type: str
    ) -> int:
        """
        檢查並標記重複的歌曲

        會在每個 track_data 中加入 'is_duplicated' 字段

        重複包含：
        1. 內部重複（歌單內有相同歌曲）
        2. 與其他非實驗歌單重複
        3. member_favorite 與 discover_weekly 互相重複

        :param tracks_data: Spotify API 返回的歌曲數據（會被修改，加入 is_duplicated 字段）
        :param current_playlist_type: 當前正在處理的歌單類型
        :return: 有效歌曲數量（不重複的歌曲數）
        """
        # 取得該 member 的其他非實驗歌單中的所有歌曲
        other_non_experiment_playlists = (
            Playlist.objects.filter(member=self.member)
            .exclude(type=Playlist.TypeOptions.EXPERIMENT)
            .exclude(type=current_playlist_type)  # 排除當前正在處理的類型
        )

        other_playlists_track_ids = set(
            other_non_experiment_playlists.values_list(
                'playlist_tracks__track__external_id', flat=True
            )
        )

        # 檢查內部重複和與其他歌單的重複
        seen_track_ids = set()
        valid_track_count = 0

        for track_data in tracks_data:
            track_external_id = track_data.get('id')

            # 檢查是否重複（內部重複或與其他非實驗歌單重複）
            is_duplicated = (
                track_external_id in seen_track_ids
                or track_external_id in other_playlists_track_ids
            )
            track_data['is_duplicated'] = is_duplicated
            seen_track_ids.add(track_external_id)

            # 只有不重複的歌曲才算有效
            if not is_duplicated:
                valid_track_count += 1

        return valid_track_count

    def _validate_member_favorite_playlist(
        self, tracks_data: list
    ) -> PlaylistSchemas.ValidationResult:
        """
        驗證 member_favorite 歌單

        規則：
        - 至少 12 首歌（排除重複的歌曲）
        - 重複包含：內部重複、與其他非實驗歌單重複、與 discover_weekly 重複
        """
        from playlist.constants import PlaylistConfig

        valid_track_count = self._mark_tracks_as_duplicated(
            tracks_data, Playlist.TypeOptions.MEMBER_FAVORITE
        )

        track_count = len(tracks_data)
        required_minimum = PlaylistConfig.MIN_FAVORITE_TRACKS
        validation_errors = []

        if valid_track_count < required_minimum:
            validation_errors.append(
                f"Member Favorite 歌單需要至少 {required_minimum} 首有效歌曲（不重複），"
                f"目前共有 {track_count} 首歌，其中 {valid_track_count} 首有效"
            )

        return PlaylistSchemas.ValidationResult(
            is_valid=len(validation_errors) == 0,
            track_count=track_count,
            valid_track_count=valid_track_count,
            required_minimum=required_minimum,
            playlist_type='member_favorite',
            tracks=self._format_tracks_info(tracks_data),
            validation_errors=validation_errors,
        )

    def _validate_discover_weekly_playlist(
        self, tracks_data: list
    ) -> PlaylistSchemas.ValidationResult:
        """
        驗證 discover_weekly 歌單

        規則：
        - 至少 20 首歌（排除重複的歌曲）
        - 重複包含：內部重複、與其他非實驗歌單重複、與 member_favorite 重複
        """
        from playlist.constants import PlaylistConfig

        valid_track_count = self._mark_tracks_as_duplicated(
            tracks_data, Playlist.TypeOptions.DISCOVER_WEEKLY
        )

        track_count = len(tracks_data)
        required_minimum = PlaylistConfig.MIN_DISCOVER_TRACKS
        validation_errors = []

        if valid_track_count < required_minimum:
            validation_errors.append(
                f"Discover Weekly 歌單需要至少 {required_minimum} 首有效歌曲（不重複），"
                f"目前共有 {track_count} 首歌，其中 {valid_track_count} 首有效"
            )

        return PlaylistSchemas.ValidationResult(
            is_valid=len(validation_errors) == 0,
            track_count=track_count,
            valid_track_count=valid_track_count,
            required_minimum=required_minimum,
            playlist_type='discover_weekly',
            tracks=self._format_tracks_info(tracks_data),
            validation_errors=validation_errors,
        )

    def _format_tracks_info(self, tracks_data: list) -> list:
        """將 Spotify API 返回的歌曲數據格式化為簡潔格式"""
        tracks_info = []
        for idx, track_data in enumerate(tracks_data, start=1):
            artists_names = [
                artist.get('name', 'Unknown')
                for artist in track_data.get('artists', [])
            ]

            # 取得專輯封面圖片 URL（選擇中等大小的圖片）
            album = track_data.get('album', {})
            images = album.get('images', [])
            image_url = (
                images[1]['url']
                if len(images) > 1
                else (images[0]['url'] if images else None)
            )

            tracks_info.append(
                PlaylistSchemas.TrackInfo(
                    order=idx,
                    name=track_data.get('name', 'Unknown'),
                    artists=artists_names,
                    external_id=track_data.get('id', ''),
                    image_url=image_url,
                    is_duplicated=track_data.get('is_duplicated', False),
                )
            )
        return tracks_info

    def _get_deduped_track_ids(self, tracks_data: list, playlist_type: str) -> list:
        """
        從 tracks_data 中提取去重後的 track IDs

        會先調用 mark_tracks_as_duplicated 標記重複，然後只返回未重複的 track IDs

        :param tracks_data: Spotify API 返回的 tracks 數據
        :param playlist_type: 歌單類型
        :return: 去重後的 track IDs 列表（保持順序）
        """
        # 標記重複的歌曲
        self._mark_tracks_as_duplicated(tracks_data, playlist_type)

        # 只收集未重複的 track IDs
        deduped_track_ids = [
            track['id']
            for track in tracks_data
            if not track.get('is_duplicated', False)
        ]

        return deduped_track_ids

    def _reorder_tracks_by_cache(
        self, tracks_data: list, cached_track_ids: list
    ) -> list:
        """
        根據緩存的 track IDs 順序重新排序 tracks_data

        :param tracks_data: Spotify API 返回的 tracks 數據
        :param cached_track_ids: 緩存的 track IDs 列表（順序）
        :return: 重新排序後的 tracks_data
        """
        # 建立 track_id -> track_data 的映射
        track_map = {track['id']: track for track in tracks_data}

        # 按照緩存的順序重新排序
        reordered_tracks = []
        for track_id in cached_track_ids:
            if track_id in track_map:
                reordered_tracks.append(track_map[track_id])

        return reordered_tracks

    def _import_or_update_playlist(
        self, spotify_playlist_id: str, playlist_type: str, tracks_data: list
    ) -> Playlist:
        """
        導入或更新指定類型的歌單

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型 (MEMBER_FAVORITE 或 DISCOVER_WEEKLY)
        :param tracks_data: Spotify API 返回的 tracks 數據
        :return: Playlist object
        """
        # 1. 獲取或創建歌單
        type_descriptions = {
            Playlist.TypeOptions.MEMBER_FAVORITE: 'Favorite Playlist',
            Playlist.TypeOptions.DISCOVER_WEEKLY: 'Discover Weekly',
        }
        description = f"{type_descriptions.get(playlist_type, 'Playlist')} - {timezone.now().strftime('%Y-%m-%d')}"

        playlist, created = Playlist.objects.get_or_create_for_member(
            member=self.member,
            playlist_type=playlist_type,
            spotify_playlist_id=spotify_playlist_id,
            description=description,
        )

        # 2. 創建 Artists 和 Tracks
        artists_data = parse_artists_from_tracks(tracks_data)
        tracks_schemas = parse_tracks(tracks_data)

        artists_map = Artist.objects.bulk_create_from_data(artists_data, self.provider)
        tracks_map = Track.objects.bulk_create_from_data(
            tracks_schemas, artists_map, self.provider
        )

        # 3. 準備要添加的 tracks（按照 tracks_data 的順序）
        tracks_to_add = []
        for track_data in tracks_data:
            track_id = track_data.get('id')
            track = tracks_map.get(track_id)
            if track:
                tracks_to_add.append(track)

        # 4. 添加 tracks 到 playlist（含去重、排序）
        added_count = self._add_tracks_with_reorder(playlist, tracks_to_add)

        logger.info(
            f"{'Created' if created else 'Updated'} {playlist_type} playlist {playlist.id} "
            f"with {added_count} new tracks for member {self.member.id}"
        )

        return playlist

    def _add_tracks_with_reorder(self, playlist: Playlist, tracks: list) -> int:
        """
        添加歌曲並重新排序

        :param playlist: Playlist instance
        :param tracks: List[Track] Track 對象列表
        :return: 新增的歌曲數量
        """
        with transaction.atomic():
            # 1. 獲取已存在的 track IDs
            existing_track_ids = set(
                playlist.playlist_tracks.values_list('track_id', flat=True)
            )

            # 2. 收集要刪除的 PlaylistTrack IDs（重複的）
            tracks_to_delete_ids = []
            new_tracks = []

            for track in tracks:
                if track.id in existing_track_ids:
                    # 刪除舊的，重新加入
                    pt = playlist.playlist_tracks.filter(track=track).first()
                    if pt:
                        tracks_to_delete_ids.append(pt.id)

                new_tracks.append(track)

            # 3. 刪除重複的舊歌（直接用 ORM）
            if tracks_to_delete_ids:
                PlaylistTrack.objects.filter(id__in=tracks_to_delete_ids).delete()

            # 4. 批量創建 PlaylistTrack（直接用 ORM）
            tracks_to_add = [
                PlaylistTrack(
                    playlist=playlist,
                    track=track,
                    order=idx + 1,
                    is_favorite=False,
                )
                for idx, track in enumerate(new_tracks)
            ]
            PlaylistTrack.objects.bulk_create(tracks_to_add, ignore_conflicts=True)

            # 5. 重新整理所有歌曲的 order（直接用 ORM）
            all_playlist_tracks = list(
                playlist.playlist_tracks.all()
                .annotate(created_minute=TruncMinute('created_at'))
                .order_by('-created_minute', 'order')
            )
            for idx, pt in enumerate(all_playlist_tracks, start=1):
                pt.order = idx

            PlaylistTrack.objects.bulk_update(all_playlist_tracks, ['order'])

            return len(tracks_to_add)
