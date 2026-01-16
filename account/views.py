from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated

from account.jwt import JWTService
from account.models import Member
from account.permissions import IsStaff
from account.serializers import (
    LoginSerializer,
    MemberSerializer,
    MemberSimpleSerializer,
    RefreshTokenSerializer,
)
from provider.models import MemberAPIToken
from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse, APISuccessResponse
from utils.views import BaseAPIView, BaseGenericViewSet


class LoginView(BaseAPIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            member = Member.objects.select_related('user').get(email=email)
        except Member.DoesNotExist:
            return APIFailedResponse(
                code=ResponseCode.USER_NOT_FOUND,
                msg=ResponseMessage.USER_NOT_FOUND,
                details={'email': email},
            )

        # 檢查 member 是否啟用
        if not member.user.is_active:
            return APIFailedResponse(
                code=ResponseCode.USER_INACTIVE,
                msg='用戶已被停用',
            )

        # 使用新的 JWTService 創建 tokens
        jwt_tokens = JWTService.create_tokens(member)
        return APISuccessResponse(data={'member_id': member.id, **jwt_tokens})


class RefreshTokenView(BaseAPIView):
    def post(self, request):
        """Token 刷新 API"""
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data['refresh_token']
        result = JWTService.refresh_access_token(refresh_token)

        if not result:
            return APIFailedResponse(
                code=ResponseCode.INVALID_TOKEN,
                msg='無效的 refresh token',
            )

        return APISuccessResponse(data=result)


class LogoutView(BaseAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """登出 API - 將 token 加入黑名單"""
        token = request.auth
        success = JWTService.blacklist_token(token)

        if success:
            return APISuccessResponse()
        else:
            return APIFailedResponse(
                code=ResponseCode.INVALID_TOKEN,
                msg='無效的 token',
            )


class MemberViewSet(
    ListModelMixin, CreateModelMixin, RetrieveModelMixin, BaseGenericViewSet
):
    permission_classes = [IsStaff]
    serializer_class = MemberSerializer
    queryset = Member.objects.filter(role=Member.RoleOptions.MEMBER)

    @action(detail=False, methods=['get'], url_path='unauthorized')
    def unauthorized(self, request):
        """列出沒有通過 Spotify 驗證的 member"""
        authorized_member_ids = (
            MemberAPIToken.objects.exclude(_access_token__isnull=True)
            .exclude(_access_token='')
            .exclude(_refresh_token__isnull=True)
            .exclude(_refresh_token='')
            .values_list('member_id', flat=True)
        )

        unauthorized_members = self.get_queryset().exclude(
            id__in=authorized_member_ids,
            spotify_provider__isnull=False,
        )

        serializer = MemberSimpleSerializer(unauthorized_members, many=True)
        return APISuccessResponse(data=serializer.data)
