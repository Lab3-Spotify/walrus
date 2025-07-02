import logging
from functools import cached_property

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from listening_profile.models import TrackHistoryPlayLog
from provider.handlers.base import BaseAPIProviderHandler, BaseAuthProviderHandler
from provider.interfaces.spotify import (
    SpotifyAPIProviderInterface,
    SpotifyAuthProviderInterface,
)
from provider.models import MemberAPIToken
from provider.serializers import TrackHistoryPlayLogSimpleSerializer
from track.models import Artist, Track
from walrus import settings

logger = logging.getLogger(__name__)


class SpotifyAuthProviderHandler(BaseAuthProviderHandler):
    @cached_property
    def auth_interface(self):
        return SpotifyAuthProviderInterface(
            auth_type=self.provider.auth_type,
            auth_details=self.provider.auth_details,
            client_id=settings.SPOTIFY_CLIENT_ID,
            client_secret=settings.SPOTIFY_CLIENT_SECRET,
        )

    def get_authorize_url(self, request):
        redirect_uri = self._get_redirect_uri(request)
        return self.auth_interface.get_authorize_url(
            redirect_uri=redirect_uri,
            scope=self._format_auth_scope(
                self.provider.extra_details.get('auth_scope', [])
            ),
            state=request.user.member.id,
        )

    def handle_authorize_callback(self, request):
        redirect_uri = self._get_redirect_uri(request)
        return self.auth_interface.handle_authorize_callback(
            request, redirect_uri=redirect_uri
        )

    def extract_token_fields(self, token_data):
        return {
            'member_id': token_data.get('member_id', None),
            'access_token': token_data.get('access_token', None),
            'refresh_token': token_data.get('refresh_token', None),
            'expires_in': token_data.get('expires_in', 3600),
        }

    def _get_redirect_uri(self, request):
        if settings.ENV == 'local':
            return 'http://127.0.0.1:8000/callback'
        else:
            url_path = reverse('provider:spotify-auth-authorize-callback')
            https_url = f"https://{request.get_host()}{url_path}"
            return https_url

    def _format_auth_scope(self, scope):
        return ' '.join(scope)


class SpotifyAPIProviderHandler(BaseAPIProviderHandler):
    @cached_property
    def api_interface(self):
        return SpotifyAPIProviderInterface(
            provider=self.provider,
            access_token=self.get_access_token(),
        )

    SPOTIFY_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
    SPOTIFY_DATETIME_FORMAT_NO_MS = '%Y-%m-%dT%H:%M:%SZ'

    def collect_recently_played_logs(self, days):
        # collect logs from days ago to now from Spotify API
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

        # remove duplicate items
        unique_keys = set()
        distinct_items = []
        for item in all_items:
            track_id = item.get('track', {}).get('id')
            played_at = item.get('played_at')
            key = (track_id, played_at)
            if key not in unique_keys:
                unique_keys.add(key)
                distinct_items.append(item)

        # validate items
        valid_items = []
        for item in distinct_items:
            serializer = TrackHistoryPlayLogSimpleSerializer(data=item)
            if serializer.is_valid():
                valid_items.append(serializer.validated_data)
            else:
                logger.warning(
                    f"TrackHistoryPlayLogSimpleSerializer is not valid: {serializer.errors}"
                )

        # create Artist, Track and TrackHistoryPlayLog instances
        artist_map = {}
        track_map = {}
        artists_to_create = []
        tracks_to_create = []
        for item in valid_items:
            track_data = item['track']
            played_at = item['played_at']
            artists = []
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
                artists.append(artist_map[key])

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

        # --- bulk create Artist, Track and TrackHistoryPlayLog ---
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
            for item in valid_items:
                track_data = item['track']
                key = (track_data['external_id'], self.provider.id)
                track_obj = track_db_map[key]
                artist_ids = [
                    artist_db_map[(a['external_id'], self.provider.id)].id
                    for a in track_data['artists']
                ]
                track_obj.artists.set(artist_ids)

            playlog_keys = set()
            for item in valid_items:
                track_data = item['track']
                played_at = item['played_at']
                track_obj = track_db_map[(track_data['external_id'], self.provider.id)]
                key = (self.member.id, track_obj.id, self.provider.id, played_at)
                playlog_keys.add(key)

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
            TrackHistoryPlayLog.objects.bulk_create(to_create)
            new_artist_external_ids = list({a.external_id for a in artists_to_create})
            if new_artist_external_ids:
                from provider.tasks import update_artists_details

                update_artists_details.delay(
                    new_artist_external_ids, self.provider.id, self.member.id
                )
        return to_create

    def refresh_token(self):
        member_api_token = MemberAPIToken.objects.filter(
            member=self.member, provider=self.provider
        ).first()
        if not member_api_token or not member_api_token.refresh_token:
            return None
        auth_handler = SpotifyAuthProviderHandler(self.provider)
        refresh_result = auth_handler.auth_interface.refresh_access_token(
            member_api_token.refresh_token
        )

        # Spotify won't return refresh_token, so we need to use the old one
        token_data = {
            **refresh_result,
            'member_id': self.member.id,
            'refresh_token': member_api_token.refresh_token,
        }
        result = auth_handler.process_token(request=None, token_data=token_data)
        return result.get('access_token')
