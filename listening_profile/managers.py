from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from django.db import models

from listening_profile.schemas import PlayLogSchemas

if TYPE_CHECKING:
    from account.models import Member
    from listening_profile.models import HistoryPlayLog, HistoryPlayLogContext
    from provider.models import Provider
    from track.models import Track


class HistoryPlayLogManager(models.Manager):
    def bulk_create_deduplicated(
        self,
        playlogs_data: List[PlayLogSchemas.CreateData],
        tracks_map: Dict[str, Track],
        context_map: Dict[tuple, HistoryPlayLogContext],
        member: Member,
        provider: Provider,
    ) -> List[HistoryPlayLog]:
        """
        批量創建 PlayLogs（自動去重）

        :param playlogs_data: List[PlayLogSchemas.CreateData]
        :param tracks_map: {external_id: Track} from Track.objects.bulk_create_from_data()
        :param context_map: {(type, external_id): HistoryPlayLogContext}
        :param member: Member instance
        :param provider: Provider instance
        :return: 創建的 HistoryPlayLog 對象列表
        """
        # 1. 查詢已存在的記錄
        played_at_list = [data.played_at for data in playlogs_data]
        existing_keys = set(
            self.filter(
                member=member,
                provider=provider,
                played_at__in=played_at_list,
            ).values_list('member_id', 'track_id', 'provider_id', 'played_at')
        )

        # 2. 過濾出不存在的
        to_create = []
        for data in playlogs_data:
            track = tracks_map.get(data.track_external_id)
            if not track:
                continue

            key = (member.id, track.id, provider.id, data.played_at)
            if key not in existing_keys:
                # 從 context_map 取得 context
                context_obj = None
                if data.context_type and data.context_external_id:
                    context_key = (data.context_type, data.context_external_id)
                    context_obj = context_map.get(context_key)

                to_create.append(
                    self.model(
                        member=member,
                        track=track,
                        provider=provider,
                        played_at=data.played_at,
                        context=context_obj,
                    )
                )

        # 3. 批量創建並返回對象列表
        created = self.bulk_create(to_create)

        return created
