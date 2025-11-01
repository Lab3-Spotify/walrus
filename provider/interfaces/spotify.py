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

    def get_current_user_playlists(self, limit=50, offset=0):
        """
        取得當前用戶的所有歌單
        :param limit: 返回的最大項目數 (default: 50, max: 50)
        :param offset: 偏移量
        :return: dict (Spotify API response)
        """
        endpoint = 'me/playlists'
        params = {'limit': limit, 'offset': offset}
        return self.handle_request('GET', endpoint, params=params)

    def get_playlist(self, playlist_id, fields=None):
        """
        取得特定歌單的詳細資訊
        :param playlist_id: Spotify playlist ID
        :param fields: 指定要返回的欄位（可選）
        :return: dict (Spotify API response)
        """
        endpoint = f'playlists/{playlist_id}'
        params = {}
        if fields:
            params['fields'] = fields
        return self.handle_request('GET', endpoint, params=params)

    def get_playlist_tracks(self, playlist_id, limit=50, offset=0, market=None):
        """
        取得歌單中的所有曲目
        :param playlist_id: Spotify playlist ID
        :param limit: 返回的最大項目數 (default: 50, max: 50)
        :param offset: 偏移量
        :param market: ISO 3166-1 alpha-2 country code (e.g., 'TW')
        :return: dict (Spotify API response)
        """
        endpoint = f'playlists/{playlist_id}/tracks'
        params = {'limit': limit, 'offset': offset}
        if market:
            params['market'] = market
        return self.handle_request('GET', endpoint, params=params)

    def search(self, query, search_type='playlist', limit=1, offset=0):
        """
        搜尋歌單、曲目、藝人等
        :param query: 搜尋關鍵字
        :param search_type: 搜尋類型 (playlist, track, artist, album, show, episode)
        :param limit: 返回的最大項目數 (default: 1, max: 50)
        :param offset: 偏移量
        :return: dict (Spotify API response)
        """
        endpoint = 'search'
        params = {'q': query, 'type': search_type, 'limit': limit, 'offset': offset}
        return self.handle_request('GET', endpoint, params=params)

    def get_user_top_tracks(self, time_range='medium_term', limit=50, offset=0):
        """
        取得用戶的 Top Tracks
        :param time_range: 時間範圍 (short_term: 4週, medium_term: 6個月, long_term: 1年左右)
        :param limit: 返回的最大項目數 (default: 50, max: 50)
        :param offset: 偏移量
        :return: dict (Spotify API response)
        """
        endpoint = 'me/top/tracks'
        params = {'time_range': time_range, 'limit': limit, 'offset': offset}
        return self.handle_request('GET', endpoint, params=params)
