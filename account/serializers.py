from rest_framework import serializers

from account.models import ExperimentGroup, Member
from provider.models import Provider


class MemberSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'email', 'role']
        read_only_fields = ['id', 'email', 'role']


class MemberSerializer(serializers.ModelSerializer):
    """Member 序列化器，用於 list/create/retrieve"""

    email = serializers.EmailField(required=True)
    name = serializers.CharField(required=True, max_length=100)
    role = serializers.ChoiceField(
        choices=[Member.RoleOptions.MEMBER],
        required=True,
    )
    experiment_group = serializers.PrimaryKeyRelatedField(
        queryset=ExperimentGroup.objects.all(),
        required=True,
    )
    spotify_provider = serializers.PrimaryKeyRelatedField(
        queryset=Provider.objects.all(),
        required=True,
    )

    class Meta:
        model = Member
        fields = [
            'id',
            'email',
            'name',
            'role',
            'experiment_group',
            'spotify_provider',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_email(self, value):
        if Member.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email is already in use')
        return value


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
