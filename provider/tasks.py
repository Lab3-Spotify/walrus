from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import Q

from account.models import Member
from provider.handlers.spotify import SpotifyAPIProviderHandler
from provider.models import Provider
from track.models import Artist
from track.serializers import ArtistSerializer
from track.services.model_helpers import bulk_create_genres
from walrus import settings

logger = get_task_logger(__name__)


@shared_task(queue='playlog_q')
def update_artists_details(artist_ids, provider_id, member_id):
    if not artist_ids:
        return []

    provider = Provider.objects.get(id=provider_id)
    member = Member.objects.get(id=member_id)
    handler = SpotifyAPIProviderHandler(provider, member=member)
    artists_data = handler.api_interface.get_several_artists(artist_ids)

    artists_external_id_mapping = {
        a.external_id: a
        for a in Artist.objects.filter(external_id__in=artist_ids, provider=provider)
    }

    all_genre_dicts = []
    for artist_data in artists_data.get('artists', []):
        for genre_name in artist_data.get('genres', []):
            all_genre_dicts.append({'name': genre_name, 'category': None})

    genre_map = bulk_create_genres(all_genre_dicts, provider_id)

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
        Artist.objects.bulk_update(artists_to_update, ['popularity', 'followers_count'])
        logger.info(
            f"Bulk updated {len(artists_to_update)} artists with popularity, followers_count, and genres."
        )
    else:
        logger.info('No artists to bulk update.')
    return [a.external_id for a in artists_to_update]


@shared_task(queue='playlog_q')
def check_and_update_missing_artist_details():
    member_id = Member.objects.filter(role=Member.ROLE_STAFF).first().id
    for provider_id in list(Provider.objects.all().values_list('id', flat=True)):
        artists = Artist.objects.filter(provider_id=provider_id).filter(
            Q(popularity__isnull=True) | Q(followers_count__isnull=True)
        )
        artist_ids = list(artists.values_list('external_id', flat=True))
        if artist_ids:
            update_artists_details.s(artist_ids, provider_id, member_id).apply_async(
                queue='playlog_q'
            )


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue='playlog_q')
def collect_member_recently_played_logs(self, provider_id, member_id):
    try:
        provider = Provider.objects.get(id=provider_id)
        member = Member.objects.get(id=member_id)
        handler = SpotifyAPIProviderHandler(provider, member)
        # Spotify can only get up to 1 day of recently played logs
        handler.collect_recently_played_logs(days=3)
        logger.info(f"Collected logs for member {member.id}")
    except Exception as e:
        logger.warning(f"Failed to collect logs for member {member_id}: {e}")
        raise self.retry(exc=e)


@shared_task(queue='playlog_q')
def collect_all_members_recently_played_logs():
    provider = Provider.objects.get(code=Provider.PROVIDER_CODE_SPOTIFY)
    members = Member.objects.filter(api_tokens__provider=provider)
    for member in members:
        collect_member_recently_played_logs.delay(provider.id, member.id)
