from rest_framework import status
from rest_framework.renderers import JSONRenderer

from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse, APISuccessResponse


class WalrusRenderer(JSONRenderer):
    """
    統一 API 回應格式的 Renderer
    自動將 DRF 標準回應轉換為我們的 APISuccessResponse/APIFailedResponse 格式
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        將 DRF 標準回應轉換為統一格式
        """
        if not renderer_context:
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get('response')
        if not response:
            return super().render(data, accepted_media_type, renderer_context)

        # 檢查是否已經是統一格式（包含 code 欄位）
        if isinstance(data, dict) and 'code' in data:
            return super().render(data, accepted_media_type, renderer_context)

        # 獲取狀態碼
        status_code = response.status_code

        # 判斷是否成功
        is_success = status_code < 400

        if is_success:
            # 使用 APISuccessResponse 格式
            success_response = APISuccessResponse(
                data=data,
                code=ResponseCode.SUCCESS,
                msg=ResponseMessage.SUCCESS,
            )
            # 更新原始 response 的 status code 為 200
            response.status_code = status.HTTP_200_OK
            return super().render(
                success_response.data, accepted_media_type, renderer_context
            )
        else:
            # 使用 APIFailedResponse 格式
            failed_response = APIFailedResponse(
                code=self._map_status_to_code(status_code),
                msg=self._get_error_message(status_code, data),
                details=self._format_errors(data),
            )
            # 更新原始 response 的 status code 為 200
            response.status_code = status.HTTP_200_OK
            return super().render(
                failed_response.data, accepted_media_type, renderer_context
            )

    def _get_error_message(self, status_code, data):
        """根據狀態碼獲取錯誤訊息"""
        if status_code == status.HTTP_400_BAD_REQUEST:
            return ResponseMessage.VALIDATION_ERROR
        elif status_code == status.HTTP_401_UNAUTHORIZED:
            return ResponseMessage.UNAUTHORIZED
        elif status_code == status.HTTP_403_FORBIDDEN:
            return ResponseMessage.FORBIDDEN
        elif status_code == status.HTTP_404_NOT_FOUND:
            return ResponseMessage.NOT_FOUND
        elif status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            return ResponseMessage.METHOD_NOT_ALLOWED
        elif status_code == status.HTTP_409_CONFLICT:
            return ResponseMessage.CONFLICT
        elif status_code >= 500:
            return ResponseMessage.INTERNAL_ERROR

        # 嘗試從 data 中提取錯誤訊息
        if isinstance(data, dict):
            if 'detail' in data:
                return data['detail']
            elif 'message' in data:
                return data['message']

        return ResponseMessage.UNKNOWN_ERROR

    def _map_status_to_code(self, status_code):
        """將 HTTP 狀態碼映射到我們的錯誤碼"""
        mapping = {
            status.HTTP_400_BAD_REQUEST: ResponseCode.VALIDATION_ERROR,
            status.HTTP_401_UNAUTHORIZED: ResponseCode.UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN: ResponseCode.FORBIDDEN,
            status.HTTP_404_NOT_FOUND: ResponseCode.NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED: ResponseCode.METHOD_NOT_ALLOWED,
            status.HTTP_409_CONFLICT: ResponseCode.CONFLICT,
            status.HTTP_500_INTERNAL_SERVER_ERROR: ResponseCode.INTERNAL_ERROR,
        }
        return mapping.get(status_code, ResponseCode.UNKNOWN_ERROR)

    def _format_errors(self, data):
        """格式化錯誤資料"""
        if isinstance(data, dict):
            # DRF 序列化器錯誤格式
            if any(isinstance(v, list) for v in data.values()):
                return data
            # 單一錯誤訊息
            elif 'detail' in data or 'message' in data:
                return None
        elif isinstance(data, list):
            return {'non_field_errors': data}

        return data if data else None
