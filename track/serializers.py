from rest_framework import serializers

from track.models import Artist, Genre, Track


class GenreSerializer(serializers.Serializer):
    name = serializers.CharField()
    category = serializers.CharField(required=False)

    class Meta:
        model = Genre
        fields = ['name', 'category']


class ArtistSerializer(serializers.Serializer):
    external_id = serializers.CharField()
    name = serializers.CharField()
    popularity = serializers.IntegerField(required=False)
    followers_count = serializers.IntegerField(required=False)
    genres = GenreSerializer(many=True, read_only=True, required=False)

    class Meta:
        model = Artist
        fields = ['external_id', 'name', 'popularity', 'followers_count', 'genres']


class TrackSerializer(serializers.Serializer):
    external_id = serializers.CharField()
    name = serializers.CharField()
    is_playable = serializers.BooleanField(required=False)
    popularity = serializers.IntegerField(required=False)
    isrc = serializers.CharField(required=False, allow_null=True)
    artists = ArtistSerializer(many=True)

    class Meta:
        model = Track
        fields = ['external_id', 'name', 'is_playable', 'popularity', 'isrc', 'artists']


class TrackSimpleSerializer(serializers.ModelSerializer):
    """簡單的 Track serializer，包含歌曲基本資訊和 clip 時間"""

    artists = serializers.SerializerMethodField()
    clip_start_ms = serializers.IntegerField(read_only=True)
    clip_end_ms = serializers.IntegerField(read_only=True)

    class Meta:
        model = Track
        fields = ['name', 'artists', 'external_id', 'clip_start_ms', 'clip_end_ms']

    def get_artists(self, obj):
        """取得歌曲的所有藝術家名稱"""
        return [artist.name for artist in obj.artists.all()]
