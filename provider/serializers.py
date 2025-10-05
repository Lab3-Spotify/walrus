from datetime import datetime

from rest_framework import serializers

from account.serializers import MemberSimpleSerializer
from provider.models import ProviderProxyAccount
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


class ProviderProxyAccountSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    provider_code = serializers.CharField(source='provider.code', read_only=True)
    is_available = serializers.SerializerMethodField()
    current_member = MemberSimpleSerializer(read_only=True)

    class Meta:
        model = ProviderProxyAccount
        fields = [
            'id',
            'code',
            'name',
            'provider_code',
            'provider_name',
            'is_active',
            'is_available',
            'current_member',
        ]
        read_only_fields = ['id', 'code', 'name', 'provider_code', 'provider_name']

    def get_is_available(self, obj):
        return obj.current_member is None
