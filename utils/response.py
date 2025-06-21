from rest_framework import status
from rest_framework.response import Response

from utils.constants import ResponseCode


class APISuccessResponse(Response):
    def __init__(
        self,
        *,
        code: int = ResponseCode.SUCCESS,
        data: dict = None,
        msg: str = '',
        status_code: int = status.HTTP_200_OK,
        headers: dict = None,
    ):
        payload = {'code': code, 'data': data or {}, 'msg': msg}

        super().__init__(data=payload, status=status_code, headers=headers)


class APIFailedResponse(Response):
    def __init__(
        self,
        *,
        code: int,
        msg: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        **kwargs,
    ):
        payload = {'code': code, 'data': {}, 'msg': msg}
        super().__init__(data=payload, status=status_code)
