from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from account.jwt import JWTService
from account.models import Member
from account.serializers import (
    LoginSerializer,
    LogoutSerializer,
    RefreshTokenSerializer,
)
from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse, APISuccessResponse
from utils.views import BaseAPIView


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
