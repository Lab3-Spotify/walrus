from datetime import datetime

from rest_framework import serializers

from track.serializers import TrackSerializer


class TrackHistoryPlayLogSimpleSerializer(serializers.Serializer):
    track = TrackSerializer(required=False)
    played_at = serializers.DateTimeField()

    def to_internal_value(self, data):
        data['track']['external_id'] = data['track'].pop('id')
        data['track']['artists'] = [
            {'external_id': artist['id'], 'name': artist['name']}
            for artist in data['track']['artists']
        ]

        data['played_at'] = datetime.fromisoformat(
            data['played_at'].replace('Z', '+00:00')
        )

        return super().to_internal_value(data)
