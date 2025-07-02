from provider.exceptions import ProviderException
from provider.interfaces.base import (
    BaseAPIProviderInterface,
    BaseOAuth2ProviderAuthInterface,
)
from utils.constants import ResponseCode, ResponseMessage


class SpotifyAuthProviderInterface(BaseOAuth2ProviderAuthInterface):
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
            code=code,
            redirect_uri=redirect_uri,
            extra_headers=headers,
        )


class SpotifyAPIProviderInterface(BaseAPIProviderInterface):
    def __init__(self, provider, access_token):
        super().__init__(provider.base_url, access_token)

    def get_recently_played(self, after=None, before=None, limit=50):
        endpoint = 'me/player/recently-played'
        params = {'limit': limit}
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        return self.handle_request('GET', endpoint, params=params)

    def get_several_artists(self, artist_ids):
        """
        批次取得多個 artist 詳細資料
        :param artist_ids: List[str]
        :return: dict (Spotify API response)
        """
        endpoint = 'artists'
        params = {'ids': ','.join(artist_ids)}
        return self.handle_request('GET', endpoint, params=params)
