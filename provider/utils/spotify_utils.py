import logging

from django.db import transaction
from django.utils import timezone

from listening_profile.models import TrackHistoryPlayLog
from provider.serializers import TrackHistoryPlayLogSimpleSerializer
from track.models import Artist, Track

logger = logging.getLogger(__name__)


class SpotifyPlayLogUtils:
    """Spotify 播放記錄處理工具類"""

    SPOTIFY_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
    SPOTIFY_DATETIME_FORMAT_NO_MS = '%Y-%m-%dT%H:%M:%SZ'

    def __init__(self, api_interface, provider, member):
        self.api_interface = api_interface
        self.provider = provider
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
            serializer = TrackHistoryPlayLogSimpleSerializer(data=item)
            if serializer.is_valid():
                valid_items.append(serializer.validated_data)
            else:
                logger.warning(
                    f"TrackHistoryPlayLogSimpleSerializer is not valid: {serializer.errors}"
                )

        return valid_items

    def prepare_entities_for_creation(self, valid_items):
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
                )
                track_map[key] = track_obj
                tracks_to_create.append(track_obj)

        return artists_to_create, tracks_to_create

    def bulk_create_and_associate_entities(
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

            # 建立播放記錄
            to_create = self._create_play_logs(valid_items, track_db_map)
            TrackHistoryPlayLog.objects.bulk_create(to_create)

            return to_create, [a.external_id for a in artists_to_create]

    def _create_play_logs(self, valid_items, track_db_map):
        """建立播放記錄（私有方法）"""
        existing_logs = set(
            TrackHistoryPlayLog.objects.filter(
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
            if key not in existing_logs:
                to_create.append(
                    TrackHistoryPlayLog(
                        member=self.member,
                        track=track_obj,
                        provider=self.provider,
                        played_at=played_at,
                    )
                )
        return to_create
