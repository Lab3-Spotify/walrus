from provider.exceptions import ProviderException
from utils.constants import ResponseCode, ResponseMessage

from .base import BaseOAuth2ProviderAuthInterface


class SpotifyAuthInterface(BaseOAuth2ProviderAuthInterface):
    AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'
    TOKEN_URL = 'https://accounts.spotify.com/api/token'

    def get_authorize_url(
        self, redirect_uri, state=None, scope=None, show_dialog=False
    ):
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
        }
        if state:
            params['state'] = state
        if scope:
            params['scope'] = scope
        if show_dialog:
            params['show_dialog'] = 'true'

        return {
            'spotify_authorize_url': self.build_url_with_params(
                self.AUTHORIZE_URL, params
            )
        }

    def handle_authorize_callback(self, request, redirect_uri):
        code = request.GET.get('code')
        error = request.GET.get('error')

        if error or not code:
            raise ProviderException(
                code=ResponseCode.EXTERNAL_API_AUTHORIZATION_ERROR,
                message=ResponseMessage.EXTERNAL_API_AUTHORIZATION_ERROR,
                details={'error': error, 'code': code},
            )
        return self.exchange_token(code, redirect_uri)

    def exchange_token(self, code, redirect_uri):
        headers = self.build_token_request_headers()
        return super().exchange_token(
            token_url=self.TOKEN_URL,
            code=code,
            redirect_uri=redirect_uri,
            extra_headers=headers,
        )


# class SpotifyInterface(BaseProviderInterface):
#     """
#     Spotify 專用的 API 請求介面。
#     """
#     def get_authorize_url(self, **kwargs):
#         # 可選擇是否實作
#         pass

#     def exchange_token(self, code, **kwargs):
#         # 可選擇是否實作
#         pass

#     def refresh_token(self, refresh_token, **kwargs):
#         # 可選擇是否實作
#         pass
