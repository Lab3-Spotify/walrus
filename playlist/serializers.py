from rest_framework import serializers

from playlist.models import Playlist, PlaylistTrack
from track.serializers import TrackSimpleSerializer


class PlaylistTrackRatingSerializer(serializers.Serializer):
    """單個 PlaylistTrack 的評分 serializer"""

    playlist_track_id = serializers.IntegerField(
        required=True,
        help_text='PlaylistTrack ID',
    )
    is_ever_listened = serializers.BooleanField(
        required=True,
        help_text='Whether the track has ever been listened to',
    )
    satisfaction_score = serializers.IntegerField(
        required=True,
        min_value=1,
        max_value=10,
        help_text='Satisfaction score (1-10)',
    )
    splendid_score = serializers.IntegerField(
        required=True,
        min_value=1,
        max_value=10,
        help_text='Splendid score (1-10)',
    )


class PlaylistTrackBatchRatingSerializer(serializers.Serializer):
    """批量更新 PlaylistTrack 評分的 serializer"""

    ratings = serializers.ListField(
        child=PlaylistTrackRatingSerializer(),
        required=True,
        allow_empty=False,
        help_text='List of track ratings',
    )

    def __init__(self, *args, **kwargs):
        self.playlist = kwargs.pop('playlist', None)
        super().__init__(*args, **kwargs)

    def validate_ratings(self, value):
        """驗證 ratings 不能有重複的 playlist_track_id"""
        track_ids = [item['playlist_track_id'] for item in value]

        # 檢查重複
        if len(track_ids) != len(set(track_ids)):
            raise serializers.ValidationError(
                'Duplicate playlist_track_id found in ratings'
            )

        # 如果有 playlist，進行完整驗證
        if self.playlist:
            # 取得 playlist 中所有的 playlist_tracks
            playlist_tracks = PlaylistTrack.objects.filter(
                playlist=self.playlist
            ).values_list('id', flat=True)

            playlist_track_ids = set(playlist_tracks)
            provided_track_ids = set(track_ids)

            # 驗證所有提供的 playlist_track_id 都屬於這個 playlist
            invalid_track_ids = provided_track_ids - playlist_track_ids
            if invalid_track_ids:
                raise serializers.ValidationError(
                    {
                        'message': 'Some playlist_track_id do not belong to this playlist',
                        'invalid_track_ids': list(invalid_track_ids),
                    }
                )

            # 驗證是否包含所有歌曲的評分
            if len(provided_track_ids) != len(playlist_track_ids):
                missing_track_ids = playlist_track_ids - provided_track_ids
                raise serializers.ValidationError(
                    {
                        'message': 'All tracks in the playlist must be rated',
                        'expected_count': len(playlist_track_ids),
                        'provided_count': len(provided_track_ids),
                        'missing_track_ids': list(missing_track_ids),
                    }
                )

        return value


class PlaylistRatingSerializer(serializers.ModelSerializer):
    """更新 Playlist 評分的 serializer"""

    satisfaction_score = serializers.IntegerField(
        required=True,
        min_value=1,
        max_value=10,
        help_text='Playlist satisfaction score (1-10)',
    )

    class Meta:
        model = Playlist
        fields = ['satisfaction_score']


class PlaylistValidationSerializer(serializers.Serializer):
    """驗證 Spotify playlist 的 serializer"""

    spotify_playlist_id = serializers.CharField(
        required=True,
        help_text='Spotify playlist ID to validate',
    )
    type = serializers.ChoiceField(
        choices=[
            Playlist.TypeOptions.MEMBER_FAVORITE,
            Playlist.TypeOptions.DISCOVER_WEEKLY,
        ],
        required=True,
        help_text='Playlist type: member_favorite or discover_weekly',
    )


class PlaylistImportSerializer(serializers.Serializer):
    """接收前端傳來的 Spotify playlist ID 和類型的 serializer"""

    spotify_playlist_id = serializers.CharField(
        required=True,
        help_text='Spotify playlist ID to import',
    )
    type = serializers.ChoiceField(
        choices=[
            Playlist.TypeOptions.MEMBER_FAVORITE,
            Playlist.TypeOptions.DISCOVER_WEEKLY,
        ],
        required=True,
        help_text='Playlist type: member_favorite or discover_weekly',
    )


class PlaylistTrackSerializer(serializers.ModelSerializer):
    """Playlist Track serializer，包含完整資訊"""

    track = TrackSimpleSerializer(read_only=True)

    class Meta:
        model = PlaylistTrack
        fields = [
            'id',
            'track',
            'order',
            'is_favorite',
            'is_ever_listened',
            'satisfaction_score',
            'splendid_score',
            'created_at',
            'updated_at',
        ]


class PlaylistSerializer(serializers.ModelSerializer):
    """Playlist serializer，包含完整資訊"""

    playlist_tracks = serializers.SerializerMethodField()

    class Meta:
        model = Playlist
        fields = [
            'id',
            'type',
            'length_type',
            'favorite_track_position_type',
            'experiment_phase',
            'external_id',
            'description',
            'satisfaction_score',
            'created_at',
            'updated_at',
            'playlist_tracks',
        ]

    def get_playlist_tracks(self, obj):
        playlist_tracks = obj.playlist_tracks.all().order_by('order')
        return PlaylistTrackSerializer(playlist_tracks, many=True).data


class PlaylistOrderCacheSerializer(serializers.Serializer):
    """快取 Spotify playlist track IDs 順序的 serializer"""

    type = serializers.ChoiceField(
        choices=[
            Playlist.TypeOptions.MEMBER_FAVORITE,
            Playlist.TypeOptions.DISCOVER_WEEKLY,
        ],
        required=True,
        help_text='Playlist type: member_favorite or discover_weekly',
    )
    track_ids = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False,
        help_text='List of Spotify track IDs in order',
    )

    def validate_track_ids(self, value):
        """驗證 track_ids 不能有重複"""
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Duplicate track IDs found')
        return value
