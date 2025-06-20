from rest_framework import status
from rest_framework.response import Response as DRFResponse

from utils.constants import ResponseCode
from utils.response import APIFailedResponse


class ResponseFormatMixin:
    """
    1) 如果 view 已经返回了 APISuccessResponse / APIFailedResponse（payload 中含 code），直接放行
    2) 否则，只有在 status_code >= 400 时，自动把它转换成 APIFailedResponse
    3) status_code < 400 的情况则什么都不做，视为开发者自己调用了 APISuccessResponse
    """

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, DRFResponse):
            raw_data = response.data or {}
            status_code = response.status_code

            if isinstance(raw_data, dict) and 'code' in raw_data:
                return super().finalize_response(request, response, *args, **kwargs)

            if status_code >= 400:
                if status_code == status.HTTP_400_BAD_REQUEST and isinstance(
                    raw_data, dict
                ):
                    return super().finalize_response(
                        request,
                        APIFailedResponse(
                            code=ResponseCode.INVALID_REQUEST,
                            msg='[Default] 驗證失敗',
                            data=raw_data,
                            status_code=status_code,
                        ),
                        *args,
                        **kwargs
                    )

                mapping = {
                    status.HTTP_401_UNAUTHORIZED: ResponseCode.UNAUTHORIZED,
                    status.HTTP_403_FORBIDDEN: ResponseCode.PERMISSION_DENIED,
                    status.HTTP_404_NOT_FOUND: ResponseCode.GENERAL_NOT_FOUND,
                    status.HTTP_405_METHOD_NOT_ALLOWED: ResponseCode.METHOD_NOT_ALLOWED,
                }
                code = mapping.get(status_code, ResponseCode.INTERNAL_ERROR)
                if isinstance(raw_data, dict):
                    msg = raw_data.get('detail', '')
                else:
                    msg = str(raw_data)

                return super().finalize_response(
                    request,
                    APIFailedResponse(code=code, msg=msg, status_code=status_code),
                    *args,
                    **kwargs
                )

        return super().finalize_response(request, response, *args, **kwargs)
