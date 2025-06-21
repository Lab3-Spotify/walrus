from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.views import exception_handler

from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse


def custom_exception_handler(exc, context):
    # 先呼叫 DRF 預設的 exception handler
    response = exception_handler(exc, context)

    # 權限失敗
    if isinstance(exc, (PermissionDenied, NotAuthenticated)):
        return APIFailedResponse(
            code=ResponseCode.PERMISSION_DENIED,
            msg=ResponseMessage.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # 其他錯誤也可以自訂
    # if isinstance(exc, SomeOtherException):
    #     return APIFailedResponse(...)

    # 其他情況 fallback 到預設
    return response
