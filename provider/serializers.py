from datetime import datetime

from rest_framework import serializers

from account.serializers import MemberSimpleSerializer
from listening_profile.models import HistoryPlayLogContext
from provider.models import ProviderProxyAccount
from track.serializers import TrackSerializer


class HistoryPlayLogContextSerializer(serializers.Serializer):
    """處理 Spotify API 回傳的 context 資料"""

    type = serializers.CharField(required=True)
    external_id = serializers.CharField(required=True)
    details = serializers.JSONField(required=False, allow_null=True)

    def to_internal_value(self, data):
        """
        從 Spotify API context 格式轉換
        Input: {"type": "playlist", "uri": "spotify:playlist:xxxxx", "href": "...", ...}
        Output: {"type": "playlist", "external_id": "xxxxx", "details": null}
        """
        # 從 uri 中提取 external_id (格式: spotify:playlist:xxxxx)
        uri = data.get('uri', '')
        external_id = uri.split(':')[-1] if uri else None
        context_type = data.get('type', None)

        if not context_type or not external_id:
            raise serializers.ValidationError(
                "Context must have 'type' and valid 'uri'"
            )

        return {
            'type': context_type,
            'external_id': external_id,
            'details': None,  # 初始為 None，由 async task 更新
        }


class HistoryPlayLogSimpleSerializer(serializers.Serializer):
    track = TrackSerializer(required=False)
    played_at = serializers.DateTimeField()
    context = HistoryPlayLogContextSerializer(required=True)

    def to_internal_value(self, data):
        data['track']['external_id'] = data['track'].pop('id')
        data['track']['artists'] = [
            {'external_id': artist['id'], 'name': artist['name']}
            for artist in data['track']['artists']
        ]

        # Extract ISRC from external_ids if available
        external_ids = data['track'].get('external_ids', {})
        data['track']['isrc'] = external_ids.get('isrc', None)

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
