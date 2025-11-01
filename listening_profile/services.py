import logging

from django.db import models

from listening_profile.models import HistoryPlayLogContext
from provider.exceptions import ProviderException

logger = logging.getLogger(__name__)


class HistoryPlayLogContextService:
    """處理 HistoryPlayLogContext 的建立和查詢"""

    @staticmethod
    def bulk_get_or_create_contexts(context_data_list):
        """
        批次取得或建立 contexts（避免 N+1 查詢）

        :param context_data_list: List of dict with 'type' and 'external_id'
        :return: dict mapping (type, external_id) -> HistoryPlayLogContext instance
        """
        if not context_data_list:
            return {}

        # 收集所有 unique contexts
        unique_contexts = set()
        contexts_to_create = []

        for context_data in context_data_list:
            context_type = context_data.get('type')
            external_id = context_data.get('external_id')

            if not context_type or not external_id:
                continue

            key = (context_type, external_id)
            if key not in unique_contexts:
                unique_contexts.add(key)
                contexts_to_create.append(
                    HistoryPlayLogContext(
                        type=context_type,
                        external_id=external_id,
                    )
                )

        # 批次建立（忽略已存在的）
        if contexts_to_create:
            HistoryPlayLogContext.objects.bulk_create(
                contexts_to_create, ignore_conflicts=True
            )

        # 批次查詢所有相關的 contexts
        context_map = {}
        if unique_contexts:
            filters = models.Q()
            for context_type, external_id in unique_contexts:
                filters |= models.Q(type=context_type, external_id=external_id)

            existing_contexts = HistoryPlayLogContext.objects.filter(filters)
            for ctx in existing_contexts:
                context_map[(ctx.type, ctx.external_id)] = ctx

        return context_map

    @staticmethod
    def update_playlist_details(context_ids, api_interface):
        """
        更新 playlist context 的 details（批次處理，減少 API 呼叫次數）

        :param context_ids: List of HistoryPlayLogContext IDs
        :param api_interface: SpotifyAPIProviderInterface instance
        :return: List of updated context IDs
        """
        if not context_ids:
            return []

        # 取得需要更新的 playlist contexts
        contexts = HistoryPlayLogContext.objects.filter(
            id__in=context_ids,
            type=HistoryPlayLogContext.TypeOptions.PLAYLIST,
        )

        # 建立 external_id -> context 的 mapping
        context_map = {ctx.external_id: ctx for ctx in contexts}

        # 批次呼叫 API 並建立 external_id -> playlist_data 的 mapping
        playlist_data_map = {}
        official_playlist_ids = []

        for context in contexts:
            try:
                playlist_data = api_interface.get_playlist(context.external_id)
                playlist_data_map[context.external_id] = playlist_data
            except ProviderException as e:
                # 檢查 details 中是否有 404 相關訊息（Spotify 官方歌單會回 404）
                details = getattr(e, 'details', {})
                error_status = (
                    details.get('error', {}).get('status')
                    if isinstance(details.get('error'), dict)
                    else None
                )

                # 404 錯誤代表是 Spotify 官方歌單
                if error_status == 404 or '404' in str(details):
                    official_playlist_ids.append(context.external_id)
                    logger.info(f"Playlist {context.external_id} is official (404)")
                else:
                    logger.warning(
                        f"Failed to fetch playlist {context.external_id}: {e}, details: {details}"
                    )
            except Exception as e:
                logger.warning(
                    f"Unexpected error fetching playlist {context.external_id}: {e}"
                )

        # 批次更新 contexts
        contexts_to_update = []
        updated_ids = []

        # 更新有資料的 playlists
        for playlist_id, playlist_data in playlist_data_map.items():
            context = context_map.get(playlist_id)
            if context:
                context.details = {
                    'name': playlist_data.get('name'),
                    'owner_name': playlist_data.get('owner', {}).get('display_name'),
                    'is_public': playlist_data.get('public'),
                    'resource_type': 'user',
                }
                contexts_to_update.append(context)
                updated_ids.append(playlist_id)

        # 更新官方 playlists
        for playlist_id in official_playlist_ids:
            context = context_map.get(playlist_id)
            if context:
                context.details = {
                    'resource_type': 'official',
                }
                contexts_to_update.append(context)
                updated_ids.append(playlist_id)

        # 批次儲存
        if contexts_to_update:
            HistoryPlayLogContext.objects.bulk_update(contexts_to_update, ['details'])
            logger.info(f"Bulk updated {len(contexts_to_update)} playlist contexts")

        return updated_ids
