from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import Q

from account.models import Member
from listening_profile.models import HistoryPlayLogContext
from provider.exceptions import ProviderException
from provider.handlers.spotify import SpotifyAPIProviderHandler
from provider.models import Provider, ProviderProxyAccount
from track.models import Artist
from track.serializers import ArtistSerializer
from track.services.model_helpers import bulk_create_genres
from walrus import settings

logger = get_task_logger(__name__)


@shared_task(queue='playlog_q')
def update_artists_details(artist_ids, member_id):
    if not artist_ids:
        return []

    member = Member.objects.get(id=member_id)
    provider = member.spotify_provider

    if not provider:
        logger.error(f"Member {member_id} has no spotify_provider assigned")
        return []

    handler = SpotifyAPIProviderHandler(provider, member=member)
    artists_data = handler.api_interface.get_several_artists(artist_ids)

    artists_external_id_mapping = {
        artist.external_id: artist
        for artist in Artist.objects.filter(
            external_id__in=artist_ids,
            provider__platform=Provider.PlatformOptions.SPOTIFY,
        )
    }

    all_genre_dicts = []
    for artist_data in artists_data.get('artists', []):
        for genre_name in artist_data.get('genres', []):
            all_genre_dicts.append({'name': genre_name, 'category': None})

    genre_map = bulk_create_genres(all_genre_dicts, provider.id)

    artists_to_update = []
    for artist_data in artists_data.get('artists', []):
        serializer = ArtistSerializer(
            data={
                'external_id': artist_data.get('id'),
                'name': artist_data.get('name', ''),
                'popularity': artist_data.get('popularity'),
                'followers_count': artist_data.get('followers', {}).get('total'),
                'genres': artist_data.get('genres', []),
            }
        )
        if serializer.is_valid():
            artist = artists_external_id_mapping.get(artist_data.get('id'))
            if artist:
                artist.name = artist_data.get('name', '')
                artist.popularity = artist_data.get('popularity')
                artist.followers_count = artist_data.get('followers', {}).get('total')
                genre_objs = [
                    genre_map[name]
                    for name in artist_data.get('genres', [])
                    if name in genre_map
                ]
                if genre_objs:
                    artist.genres.set(genre_objs)
                artists_to_update.append(artist)
        else:
            logger.warning(f"Invalid artist data: {serializer.errors}")
    if artists_to_update:
        Artist.objects.bulk_update(
            artists_to_update, ['name', 'popularity', 'followers_count']
        )
        logger.info(
            f"Bulk updated {len(artists_to_update)} artists with popularity, followers_count, and genres."
        )
    else:
        logger.info('No artists to bulk update.')
    return [a.external_id for a in artists_to_update]


@shared_task(queue='playlog_q')
def check_and_update_missing_artist_details():
    """
    檢查並更新缺少詳細資訊的 artists

    分批處理以避免 Spotify API 限制（一次最多 50 個）
    """
    staff_member = Member.objects.filter(role=Member.RoleOptions.STAFF).first()
    if not staff_member:
        logger.warning('No staff member found for updating artist details')
        return

    # 查詢所有 Spotify platform 缺少詳細資訊的 artists
    artists = Artist.objects.filter(
        provider__platform=Provider.PlatformOptions.SPOTIFY
    ).filter(Q(popularity__isnull=True) | Q(followers_count__isnull=True) | Q(name=''))
    artist_ids = list(artists.values_list('external_id', flat=True))

    if not artist_ids:
        logger.info('No artists need updating')
        return

    # Spotify API 一次最多支援 50 個 artists
    batch_size = 50
    total_batches = (len(artist_ids) + batch_size - 1) // batch_size

    logger.info(
        f"Found {len(artist_ids)} artists to update, "
        f"splitting into {total_batches} batches"
    )

    for i in range(total_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, len(artist_ids))
        batch_ids = artist_ids[start_idx:end_idx]

        update_artists_details.s(batch_ids, staff_member.id).apply_async(
            queue='playlog_q'
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue='playlog_q')
def collect_member_recently_play_logs(self, member_id):
    try:
        member = Member.objects.get(id=member_id)
        provider = member.spotify_provider

        if not provider:
            logger.error(f"Member {member_id} has no spotify_provider assigned")
            return

        # 使用 Service（業務入口）
        from provider.services import SpotifyPlayLogService

        service = SpotifyPlayLogService(provider, member)
        # Spotify can only get up to 1 day of recently played logs
        service.collect_recently_played_logs(days=3)
        logger.info(f"Collected logs for member {member.id}")
    except Exception as e:
        logger.warning(f"Failed to collect logs for member {member_id}: {e}")
        raise self.retry(exc=e)


@shared_task(queue='playlog_q')
def collect_all_members_recently_played_logs():
    # 取得所有有指定 Spotify provider 的 member
    members = Member.objects.filter(
        spotify_provider__isnull=False, role=Member.RoleOptions.MEMBER
    )

    for member in members:
        collect_member_recently_play_logs.delay(member.id)


@shared_task(queue='playlog_q')
def update_playlist_context_details(context_ids, member_id):
    """
    更新 playlist context 的 details（異步任務）

    :param context_ids: List of HistoryPlayLogContext IDs
    :param member_id: Member ID (用於取得 access token)
    """
    from listening_profile.services import HistoryPlayLogContextService

    if not context_ids:
        return []

    member = Member.objects.get(id=member_id)
    provider = member.spotify_provider

    if not provider:
        logger.error(f"Member {member_id} has no spotify_provider assigned")
        return []

    handler = SpotifyAPIProviderHandler(provider, member=member)

    # 呼叫 service 處理業務邏輯
    updated = HistoryPlayLogContextService.update_playlist_details(
        context_ids, handler.api_interface
    )

    logger.info(f"Updated {len(updated)} playlist contexts")
    return updated


@shared_task(queue='playlog_q')
def check_and_update_missing_playlist_context_details():
    """
    檢查並更新缺少 details 的 playlist contexts

    定期執行，批次處理需要更新的 contexts
    """
    staff_member = Member.objects.filter(role=Member.RoleOptions.STAFF).first()
    if not staff_member:
        logger.warning('No staff member found for updating playlist context details')
        return

    # 查詢所有 playlist 類型且缺少 details 的 contexts
    contexts = HistoryPlayLogContext.objects.filter(
        type=HistoryPlayLogContext.TypeOptions.PLAYLIST
    ).filter(Q(details__isnull=True) | Q(details={}))

    context_ids = list(contexts.values_list('id', flat=True))

    if not context_ids:
        logger.info('No playlist contexts need updating')
        return

    # 批次大小設為 50（可以根據 API rate limit 調整）
    batch_size = 50
    total_batches = (len(context_ids) + batch_size - 1) // batch_size

    logger.info(
        f"Found {len(context_ids)} playlist contexts to update, "
        f"splitting into {total_batches} batches"
    )

    for i in range(total_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, len(context_ids))
        batch_ids = context_ids[start_idx:end_idx]

        update_playlist_context_details.s(batch_ids, staff_member.id).apply_async(
            queue='playlog_q'
        )
