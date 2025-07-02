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
    artists = ArtistSerializer(many=True)

    class Meta:
        model = Track
        fields = ['external_id', 'name', 'is_playable', 'popularity', 'artists']
