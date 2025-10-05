from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler

from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse

try:
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
except ImportError:
    TokenError = None
    InvalidToken = None


class ResponseFormatMixin:
    """異常處理服務類 - 提供統一的異常處理邏輯"""

    def handle_method_not_allowed_error(self, exc, context):
        """處理MethodNotAllowed錯誤"""
        return APIFailedResponse(
            code=ResponseCode.METHOD_NOT_ALLOWED,
            msg=ResponseMessage.METHOD_NOT_ALLOWED,
            details=str(exc.detail) if hasattr(exc, 'detail') else None,
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def handle_validation_error(self, exc, context):
        """處理驗證錯誤"""
        return APIFailedResponse(
            code=ResponseCode.VALIDATION_ERROR,
            msg=ResponseMessage.VALIDATION_ERROR,
            details=exc.detail,
        )

    def handle_permission_error(self, exc, context):
        """處理權限錯誤"""
        return APIFailedResponse(
            code=ResponseCode.PERMISSION_DENIED,
            msg=ResponseMessage.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    def handle_authentication_error(self, exc, context):
        """處理認證錯誤"""
        return APIFailedResponse(
            code=ResponseCode.INVALID_TOKEN,
            msg=ResponseMessage.INVALID_TOKEN,
            details=str(exc.detail) if hasattr(exc, 'detail') else None,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    def handle_jwt_error(self, exc, context):
        """處理 JWT 相關錯誤"""
        return APIFailedResponse(
            code=ResponseCode.UNAUTHORIZED,
            msg=ResponseMessage.UNAUTHORIZED,
            details=str(exc.detail.get('detail'))
            if hasattr(exc, 'detail') and exc.detail
            else None,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    def handle_exception_service(self, exc, context):
        """主要的異常處理邏輯"""
        if isinstance(exc, ValidationError):
            return self.handle_validation_error(exc, context)

        if isinstance(exc, MethodNotAllowed):
            return self.handle_method_not_allowed_error(exc, context)

        if isinstance(exc, AuthenticationFailed):
            return self.handle_authentication_error(exc, context)

        if isinstance(exc, (PermissionDenied, NotAuthenticated)):
            return self.handle_permission_error(exc, context)

        # 處理 JWT 相關異常
        if TokenError and isinstance(exc, TokenError):
            return self.handle_jwt_error(exc, context)
        if InvalidToken and isinstance(exc, InvalidToken):
            return self.handle_jwt_error(exc, context)

        # fallback 到 DRF 預設
        return exception_handler(exc, context)


def custom_exception_handler(exc, context):
    return ResponseFormatMixin().handle_exception_service(exc, context)
