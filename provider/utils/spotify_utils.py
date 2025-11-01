import logging

from django.db import models, transaction
from django.utils import timezone

from listening_profile.models import HistoryPlayLog
from listening_profile.services import HistoryPlayLogContextService
from playlist.models import Playlist, PlaylistTrack
from provider.serializers import HistoryPlayLogSimpleSerializer
from track.models import Artist, Track

logger = logging.getLogger(__name__)


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


class SpotifyDataUtils:
    """Spotify 基礎資料處理工具類 - 處理 Artists 和 Tracks 的創建"""

    def __init__(self, provider):
        self.provider = provider

    def create_artists_from_tracks(self, tracks_data):
        """從 tracks 資料中收集並創建 artists，返回 artist_id -> Artist object 的 mapping"""
        # 收集所有 artist，保留 name 資訊
        all_artists = {}
        for track_data in tracks_data:
            for artist in track_data.get('artists', []):
                artist_id = artist.get('id')
                if artist_id not in all_artists:
                    all_artists[artist_id] = artist.get('name', '')

        artists_map = {}
        for artist_id, artist_name in all_artists.items():
            artist, _ = Artist.objects.get_or_create(
                external_id=artist_id,
                provider=self.provider,
                defaults={'name': artist_name},
            )
            artists_map[artist_id] = artist

        return artists_map

    def create_or_get_track(self, track_data, artists_map):
        """創建或獲取 Track 並關聯 artists"""
        track, track_created = Track.objects.get_or_create(
            external_id=track_data.get('id'),
            provider=self.provider,
            defaults={
                'name': track_data.get('name', ''),
                'popularity': track_data.get('popularity', 0),
                'isrc': track_data.get('external_ids', {}).get('isrc', ''),
            },
        )

        if track_created:
            artist_objs = [
                artists_map[artist.get('id')]
                for artist in track_data.get('artists', [])
                if artist.get('id') in artists_map
            ]
            track.artists.set(artist_objs)

        return track

    def trigger_artist_details_update(self, artist_ids, member_id):
        """異步觸發 artist 詳細資訊更新"""
        if artist_ids:
            from provider.tasks import update_artists_details

            update_artists_details.delay(list(artist_ids), member_id)


class SpotifyPlayLogUtils(SpotifyDataUtils):
    """Spotify 播放記錄處理工具類"""

    SPOTIFY_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
    SPOTIFY_DATETIME_FORMAT_NO_MS = '%Y-%m-%dT%H:%M:%SZ'

    def __init__(self, api_interface, provider, member):
        super().__init__(provider)
        self.api_interface = api_interface
        self.member = member

    def fetch_all_recently_played_items(self, days):
        """從 Spotify API 收集所有播放記錄"""
        now = timezone.now()
        after = int((now - timezone.timedelta(days=days)).timestamp() * 1000)

        all_items = []
        next_after = after

        while True:
            data = self.api_interface.get_recently_played(after=next_after, limit=50)
            items = data.get('items', [])
            if not items:
                break

            all_items.extend(items)
            last_played = items[-1]['played_at']

            try:
                last_played_dt = timezone.datetime.strptime(
                    last_played, self.SPOTIFY_DATETIME_FORMAT
                )
            except ValueError:
                last_played_dt = timezone.datetime.strptime(
                    last_played, self.SPOTIFY_DATETIME_FORMAT_NO_MS
                )

            last_played_ts = int(last_played_dt.timestamp() * 1000)
            if last_played_ts <= next_after:
                break
            next_after = last_played_ts
            if len(items) < 50:
                break

        return all_items

    def deduplicate_and_validate_items(self, items):
        """去重並驗證播放記錄"""
        unique_keys = set()
        distinct_items = []
        for item in items:
            track_id = item.get('track', {}).get('id')
            played_at = item.get('played_at')
            key = (track_id, played_at)
            if key not in unique_keys:
                unique_keys.add(key)
                distinct_items.append(item)

        valid_items = []
        for item in distinct_items:
            serializer = HistoryPlayLogSimpleSerializer(data=item)
            if serializer.is_valid():
                valid_items.append(serializer.validated_data)
            else:
                logger.warning(
                    f"HistoryPlayLogSimpleSerializer is not valid: {serializer.errors}"
                )

        return valid_items

    def prepare_tracks_artists_data(self, valid_items):
        """準備要建立的 Artist 和 Track 實體"""
        artist_map = {}
        track_map = {}
        artists_to_create = []
        tracks_to_create = []

        for item in valid_items:
            track_data = item['track']

            # 處理 artists
            for artist_data in track_data['artists']:
                key = (artist_data['external_id'], self.provider)
                if key not in artist_map:
                    artist_obj = Artist(
                        external_id=artist_data['external_id'],
                        provider=self.provider,
                        name=artist_data['name'],
                    )
                    artist_map[key] = artist_obj
                    artists_to_create.append(artist_obj)

            # 處理 track
            key = (track_data['external_id'], self.provider)
            if key not in track_map:
                track_obj = Track(
                    external_id=track_data['external_id'],
                    provider=self.provider,
                    name=track_data['name'],
                    is_playable=track_data.get('is_playable', True),
                    popularity=track_data.get('popularity', None),
                    isrc=track_data.get('isrc', None),
                )
                track_map[key] = track_obj
                tracks_to_create.append(track_obj)

        return artists_to_create, tracks_to_create

    def bulk_create_playlogs_with_relations(
        self, artists_to_create, tracks_to_create, valid_items
    ):
        """批次建立實體並建立關聯"""
        with transaction.atomic():
            Artist.objects.bulk_create(artists_to_create, ignore_conflicts=True)
            Track.objects.bulk_create(tracks_to_create, ignore_conflicts=True)

            artist_db_map = {
                (a.external_id, a.provider_id): a
                for a in Artist.objects.filter(provider=self.provider)
            }
            track_db_map = {
                (t.external_id, t.provider_id): t
                for t in Track.objects.filter(provider=self.provider)
            }

            # 設定 track-artist 關聯
            for item in valid_items:
                track_data = item['track']
                key = (track_data['external_id'], self.provider.id)
                track_obj = track_db_map[key]
                artist_ids = [
                    artist_db_map[(a['external_id'], self.provider.id)].id
                    for a in track_data['artists']
                ]
                track_obj.artists.set(artist_ids)

            # 批次建立或取得 contexts
            context_data_list = [
                item.get('context') for item in valid_items if item.get('context')
            ]
            context_map = HistoryPlayLogContextService.bulk_get_or_create_contexts(
                context_data_list
            )

            # 建立播放記錄（包含 context 關聯）
            to_create = self._create_play_logs(valid_items, track_db_map, context_map)
            HistoryPlayLog.objects.bulk_create(to_create)

            # 觸發異步任務更新 artist details
            new_artist_external_ids = [a.external_id for a in artists_to_create]
            if new_artist_external_ids:
                from provider.tasks import update_artists_details

                update_artists_details.delay(new_artist_external_ids, self.member.id)

            # 觸發異步任務更新 playlist context details
            playlist_context_ids = [
                ctx.id
                for ctx in context_map.values()
                if ctx.type == 'playlist' and (not ctx.details or ctx.details == {})
            ]
            if playlist_context_ids:
                from provider.tasks import update_playlist_context_details

                update_playlist_context_details.delay(
                    playlist_context_ids, self.member.id
                )

            return to_create

    def _create_play_logs(self, valid_items, track_db_map, context_map):
        existing_logs = set(
            HistoryPlayLog.objects.filter(
                member=self.member,
                provider=self.provider,
                played_at__in=[item['played_at'] for item in valid_items],
            ).values_list('member_id', 'track_id', 'provider_id', 'played_at')
        )

        to_create = []
        for item in valid_items:
            track_data = item['track']
            played_at = item['played_at']
            track_obj = track_db_map[(track_data['external_id'], self.provider.id)]
            key = (self.member.id, track_obj.id, self.provider.id, played_at)

            # 從 context_map 取得 context
            context_obj = None
            context_data = item.get('context')
            if context_data:
                context_key = (
                    context_data.get('type'),
                    context_data.get('external_id'),
                )
                context_obj = context_map.get(context_key)

            if key not in existing_logs:
                to_create.append(
                    HistoryPlayLog(
                        member=self.member,
                        track=track_obj,
                        provider=self.provider,
                        played_at=played_at,
                        context=context_obj,
                    )
                )
        return to_create


class SpotifyPlaylistBaseUtils(SpotifyDataUtils):
    """Spotify 歌單處理基礎工具類 - 處理 playlist 相關的共用邏輯"""

    def __init__(self, api_interface, provider, member):
        super().__init__(provider)
        self.api_interface = api_interface
        self.member = member

    def fetch_all_playlist_tracks(self, spotify_playlist_id):
        """
        從 Spotify API 收集歌單中的所有歌曲

        使用 market='TW' 參數讓 Spotify API 直接返回台灣市場可用的歌曲
        反轉整體順序（最後一個元素變成第一個）
        注意：在所有分頁收集完畢後才反轉，確保整體順序正確
        """
        items = SpotifyPaginationHelper.fetch_all_items(
            api_method=self.api_interface.get_playlist_tracks,
            total_limit=None,
            playlist_id=spotify_playlist_id,
            market='TW',
        )

        # 提取 track 資料（排除 podcast episodes 等非 track 項目）
        # market='TW' 已經確保只返回台灣市場可用的歌曲
        tracks = [
            item['track']
            for item in items
            if item.get('track') and item['track'].get('type') == 'track'
        ]

        return tracks

    def mark_tracks_as_duplicated(self, tracks_data, current_playlist_type):
        """
        檢查並標記重複的歌曲

        會在每個 track_data 中加入 'is_duplicated' 欄位

        重複包含：
        1. 內部重複（歌單內有相同歌曲）
        2. 與其他非實驗歌單重複
        3. member_favorite 與 discover_weekly 互相重複

        :param tracks_data: Spotify API 返回的歌曲資料（會被修改，加入 is_duplicated 欄位）
        :param current_playlist_type: 當前正在處理的歌單類型
        :return: 有效歌曲數量（不重複的歌曲數）
        """
        from playlist.models import Playlist

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


class SpotifyPlaylistValidationUtils(SpotifyPlaylistBaseUtils):
    """Spotify 歌單驗證工具類 - 檢查歌單是否符合實驗要求"""

    def validate_playlist(self, spotify_playlist_id, playlist_type):
        """
        驗證 Spotify 歌單是否符合實驗要求

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型 (member_favorite 或 discover_weekly)
        :return: 驗證結果字典
        """
        tracks_data = self.fetch_all_playlist_tracks(spotify_playlist_id)

        if playlist_type == Playlist.TypeOptions.MEMBER_FAVORITE:
            return self._validate_member_favorite_playlist(tracks_data)
        elif playlist_type == Playlist.TypeOptions.DISCOVER_WEEKLY:
            return self._validate_discover_weekly_playlist(tracks_data)
        else:
            raise ValueError(f"不支援的歌單類型: {playlist_type}")

    def _validate_member_favorite_playlist(self, tracks_data):
        """
        驗證 member_favorite 歌單

        規則：
        - 至少 12 首歌（排除重複的歌曲）
        - 重複包含：內部重複、與其他非實驗歌單重複、與 discover_weekly 重複
        """
        from playlist.constants import PlaylistConfig
        from playlist.models import Playlist

        valid_track_count = self.mark_tracks_as_duplicated(
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

        return {
            'is_valid': len(validation_errors) == 0,
            'track_count': track_count,
            'valid_track_count': valid_track_count,
            'required_minimum': required_minimum,
            'playlist_type': 'member_favorite',
            'tracks': self._format_tracks_info(tracks_data),
            'validation_errors': validation_errors,
        }

    def _validate_discover_weekly_playlist(self, tracks_data):
        """
        驗證 discover_weekly 歌單

        規則：
        - 至少 20 首歌（排除重複的歌曲）
        - 重複包含：內部重複、與其他非實驗歌單重複、與 member_favorite 重複
        """
        from playlist.constants import PlaylistConfig
        from playlist.models import Playlist

        valid_track_count = self.mark_tracks_as_duplicated(
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

        return {
            'is_valid': len(validation_errors) == 0,
            'track_count': track_count,
            'valid_track_count': valid_track_count,
            'required_minimum': required_minimum,
            'playlist_type': 'discover_weekly',
            'tracks': self._format_tracks_info(tracks_data),
            'validation_errors': validation_errors,
        }

    def _format_tracks_info(self, tracks_data):
        """將 Spotify API 返回的歌曲資料格式化為簡潔格式"""
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
                {
                    'order': idx,
                    'name': track_data.get('name', 'Unknown'),
                    'artists': artists_names,
                    'external_id': track_data.get('id', ''),
                    'image_url': image_url,
                    'is_duplicated': track_data.get('is_duplicated', False),
                }
            )
        return tracks_info


class SpotifyPlaylistImportUtils(SpotifyPlaylistBaseUtils):
    """Spotify 歌單匯入處理工具類 - 處理用戶提供的 Spotify playlist 匯入"""

    def get_deduped_track_ids(self, tracks_data, playlist_type):
        """
        從 tracks_data 中提取去重後的 track IDs

        會先呼叫 mark_tracks_as_duplicated 標記重複，然後只返回未重複的 track IDs

        :param tracks_data: Spotify API 返回的 tracks 資料
        :param playlist_type: 歌單類型
        :return: 去重後的 track IDs 列表（保持順序）
        """
        # 標記重複的歌曲
        self.mark_tracks_as_duplicated(tracks_data, playlist_type)

        # 只收集未重複的 track IDs
        deduped_track_ids = [
            track['id']
            for track in tracks_data
            if not track.get('is_duplicated', False)
        ]

        return deduped_track_ids

    def reorder_tracks_by_cache(self, tracks_data, cached_track_ids):
        """
        根據快取的 track IDs 順序重新排序 tracks_data

        :param tracks_data: Spotify API 返回的 tracks 資料
        :param cached_track_ids: 快取的 track IDs 列表（順序）
        :return: 重新排序後的 tracks_data
        """
        # 建立 track_id -> track_data 的映射
        track_map = {track['id']: track for track in tracks_data}

        # 按照快取的順序重新排序
        reordered_tracks = []
        for track_id in cached_track_ids:
            if track_id in track_map:
                reordered_tracks.append(track_map[track_id])

        return reordered_tracks

    def _get_or_create_playlist(self, spotify_playlist_id, playlist_type):
        """
        取得或創建指定類型的歌單

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型
        :return: (Playlist, created)
        """
        from playlist.models import Playlist

        type_descriptions = {
            Playlist.TypeOptions.MEMBER_FAVORITE: 'Favorite Playlist',
            Playlist.TypeOptions.DISCOVER_WEEKLY: 'Discover Weekly',
        }
        description = f"{type_descriptions.get(playlist_type, 'Playlist')} - {timezone.now().strftime('%Y-%m-%d')}"

        playlist, created = Playlist.objects.get_or_create(
            member=self.member,
            type=playlist_type,
            defaults={
                'external_id': spotify_playlist_id,
                'description': description,
            },
        )

        if not created:
            playlist.external_id = spotify_playlist_id
            playlist.description = description
            playlist.save()

        return playlist, created

    def _prepare_tracks_for_import(self, playlist, tracks_data, playlist_type):
        """
        準備要匯入的歌曲（處理重複、創建 Track objects）

        注意：tracks_data 應該已經被 mark_tracks_as_duplicated 標記過
        （透過 get_deduped_track_ids 或 reorder_tracks_by_cache 調用）

        重複檢查邏輯：
        - 內部重複: 內部不可以有重複
        - 跨歌單重複: 不可以跟其他類型的非實驗歌單重複（例如 DW 不能跟 MF 重複）
        - 自身舊版本: 可以重複(會被刪除重設)

        :param playlist: Playlist object
        :param tracks_data: Spotify API 返回的 tracks 資料（已標記 is_duplicated）
        :param playlist_type: 歌單類型
        :return: (tracks_to_delete_ids, new_tracks_ordered, artists_map)
        """
        # 1. 取得歌單中已存在的歌曲（這些會被刪除）
        existing_playlist_tracks = {
            pt.track.external_id: pt
            for pt in playlist.playlist_tracks.select_related('track')
        }

        # 2. 批次創建 artists
        artists_map = self.create_artists_from_tracks(tracks_data)

        # 3. 收集要新增的 tracks（根據 is_duplicated 欄位過濾）
        tracks_to_delete_ids = []
        new_tracks_ordered = []

        for track_data in tracks_data:
            track_external_id = track_data.get('id')
            is_duplicated = track_data.get('is_duplicated', False)

            # 如果重複，跳過此歌曲
            if is_duplicated:
                # 如果歌曲已在當前歌單中，標記為刪除
                if track_external_id in existing_playlist_tracks:
                    tracks_to_delete_ids.append(
                        existing_playlist_tracks[track_external_id].id
                    )
                continue

            # 如果歌曲已在歌單中 → 標記為刪除（稍後會重新加入）
            if track_external_id in existing_playlist_tracks:
                tracks_to_delete_ids.append(
                    existing_playlist_tracks[track_external_id].id
                )

            # 創建或取得 Track
            track = self.create_or_get_track(track_data, artists_map)
            new_tracks_ordered.append(track)

        return tracks_to_delete_ids, new_tracks_ordered, artists_map

    def _add_and_reorder_tracks(
        self, playlist, tracks_to_delete_ids, new_tracks_ordered
    ):
        """
        刪除重複歌曲、新增新歌、重新排序

        :param playlist: Playlist object
        :param tracks_to_delete_ids: 要刪除的 PlaylistTrack IDs
        :param new_tracks_ordered: 要新增的 Track objects
        :return: 新增的歌曲數量
        """
        with transaction.atomic():
            # 刪除重複的舊歌
            if tracks_to_delete_ids:
                PlaylistTrack.objects.filter(id__in=tracks_to_delete_ids).delete()

            # 新增新歌（使用 API 順序作為 order）
            tracks_to_add = [
                PlaylistTrack(
                    playlist=playlist,
                    track=track,
                    order=idx + 1,
                    is_favorite=False,
                )
                for idx, track in enumerate(new_tracks_ordered)
            ]
            PlaylistTrack.objects.bulk_create(tracks_to_add, ignore_conflicts=True)

            # 重新整理所有歌曲的 order
            # 使用分鐘級別的 created_at 來區分不同次更新，避免同一次插入的歌曲被重排順序
            from django.db.models.functions import TruncMinute

            all_playlist_tracks = list(
                PlaylistTrack.objects.filter(playlist=playlist)
                .annotate(created_minute=TruncMinute('created_at'))
                .order_by('-created_minute', 'order')
            )
            for idx, pt in enumerate(all_playlist_tracks, start=1):
                pt.order = idx

            PlaylistTrack.objects.bulk_update(all_playlist_tracks, ['order'])

        return len(tracks_to_add)

    def import_or_update_playlist(
        self, spotify_playlist_id, playlist_type, tracks_data
    ):
        """
        匯入或更新指定類型的歌單

        排序邏輯：新歌 order 靠前
        - 使用 Meta.ordering = ['-created_at', 'order'] 自動排序
        - 新增時按 API 返回順序設定 order
        - 最後統一重新整理所有 order 為連續數字

        邏輯：
        - 兩種類型都只能有一個 playlist（根據 member + type 判斷）
        - 更新時保留舊歌曲，新歌排在前面
        - 重複的歌曲會被刪除後重新加入（視為新歌）
        - 自動排除與其他類型非實驗歌單重複的歌曲

        :param spotify_playlist_id: Spotify playlist ID
        :param playlist_type: 歌單類型 (MEMBER_FAVORITE 或 DISCOVER_WEEKLY)
        :param tracks_data: Spotify API 返回的 tracks 資料
        :return: Playlist object
        """
        # 1. 取得或創建歌單
        playlist, created = self._get_or_create_playlist(
            spotify_playlist_id, playlist_type
        )

        # 2. 準備要匯入的歌曲（自動排除重複）
        (
            tracks_to_delete_ids,
            new_tracks_ordered,
            artists_map,
        ) = self._prepare_tracks_for_import(playlist, tracks_data, playlist_type)

        # 3. 新增歌曲並重新排序
        added_count = self._add_and_reorder_tracks(
            playlist, tracks_to_delete_ids, new_tracks_ordered
        )

        # 4. 異步更新 artist 詳細資訊
        self.trigger_artist_details_update(artists_map.keys(), self.member.id)

        logger.info(
            f"{'Created' if created else 'Updated'} {playlist_type} playlist {playlist.id} "
            f"with {added_count} new tracks for member {self.member.id}"
        )

        return playlist
