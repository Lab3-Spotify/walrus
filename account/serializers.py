from rest_framework import serializers

from account.models import Member


class MemberSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'email', 'role']
        read_only_fields = ['id', 'email', 'role']


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    token_type = serializers.CharField()
    expires_in = serializers.IntegerField()


class LogoutSerializer(serializers.Serializer):
    token = serializers.CharField(
        help_text='Access token or refresh token to blacklist'
    )
