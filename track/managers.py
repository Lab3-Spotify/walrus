from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from django.db import models

from track.schemas import ArtistSchemas, TrackSchemas

if TYPE_CHECKING:
    from provider.models import Provider
    from track.models import Artist, Track


class ArtistManager(models.Manager):
    def bulk_create_from_data(
        self,
        artists_data: List[ArtistSchemas.CreateData],
        provider: Provider,
    ) -> Dict[str, Artist]:
        """
        批量創建 Artists

        :param artists_data: List[ArtistSchemas.CreateData]
        :param provider: Provider instance
        :return: {external_id: Artist} mapping
        """
        # 1. 創建 Model 實例
        artists_to_create = [
            self.model(
                external_id=data.external_id,
                provider=provider,
                name=data.name,
                popularity=data.popularity,
                followers_count=data.followers_count,
            )
            for data in artists_data
        ]

        # 2. 批量插入（忽略衝突）
        self.bulk_create(artists_to_create, ignore_conflicts=True)

        # 3. 查詢所有（包含已存在的）
        external_ids = [data.external_id for data in artists_data]
        all_artists = self.filter(
            external_id__in=external_ids,
            provider=provider,
        )

        # 4. 返回 mapping
        return {artist.external_id: artist for artist in all_artists}


class TrackManager(models.Manager):
    def bulk_create_from_data(
        self,
        tracks_data: List[TrackSchemas.CreateData],
        artists_map: Dict[str, Artist],
        provider: Provider,
    ) -> Dict[str, Track]:
        """
        批量創建 Tracks 並關聯 Artists

        :param tracks_data: List[TrackSchemas.CreateData]
        :param artists_map: {external_id: Artist} from Artist.objects.bulk_create_from_data()
        :param provider: Provider instance
        :return: {external_id: Track} mapping
        """
        # 1. 創建 Track 實例
        tracks_to_create = [
            self.model(
                external_id=data.external_id,
                provider=provider,
                name=data.name,
                popularity=data.popularity,
                is_playable=data.is_playable,
                isrc=data.isrc,
            )
            for data in tracks_data
        ]

        # 2. 批量插入
        self.bulk_create(tracks_to_create, ignore_conflicts=True)

        # 3. 查詢所有 Track
        external_ids = [data.external_id for data in tracks_data]
        tracks_map = {
            track.external_id: track
            for track in self.filter(
                external_id__in=external_ids,
                provider=provider,
            )
        }

        # 4. 設置 M2M 關聯
        for data in tracks_data:
            track = tracks_map.get(data.external_id)
            if not track:
                continue

            artist_objs = [
                artists_map[artist_id]
                for artist_id in data.artist_external_ids
                if artist_id in artists_map
            ]
            track.artists.set(artist_objs)

        return tracks_map
