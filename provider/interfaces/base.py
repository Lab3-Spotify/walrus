import base64
import logging
import time
from abc import ABC, abstractmethod
from urllib.parse import urlencode

import jwt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from provider.exceptions import ProviderException
from utils.constants import ResponseCode, ResponseMessage

logger = logging.getLogger(__name__)

RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 5  # sleep: 0s, 5s, 10s between retries
RETRY_STATUS_FORCELIST = [500, 502, 503, 504]


def _build_retry_session():
    session = requests.Session()
    retry = Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


class BaseHttpClient(ABC):
    def handle_request(
        self, method, url, headers=None, params=None, data=None, json=None, **kwargs
    ):
        session = _build_retry_session()
        try:
            response = session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            self.handle_error(e, getattr(e, 'response', None))

    def handle_error(self, exception, response=None):
        error_data = {}
        http_status_code = None
        if response is not None:
            http_status_code = response.status_code
            try:
                error_data = response.json()
            except Exception:
                error_data = {
                    'error': 'invalid_response',
                    'details': str(response.content),
                }

            logger.error(
                f"External API error: {exception.__class__.__name__}: {str(exception)}\n"
                f"Status Code: {response.status_code}\n"
                f"Response: {error_data}"
            )
        else:
            error_data = {'error': 'connection_error', 'details': str(exception)}
            logger.error(
                f"Connection error: {exception.__class__.__name__}: {str(exception)}\n"
                f"Details: {error_data}"
            )

        raise ProviderException(
            code=ResponseCode.EXTERNAL_API_ERROR,
            message=ResponseMessage.EXTERNAL_API_ERROR,
            details=error_data,
            status_code=http_status_code,
        )

    def build_url_with_params(self, url, params):
        return f"{url}?{urlencode(params)}"


class BaseProviderAuthInterface(BaseHttpClient, ABC):
    def __init__(self, auth_type, auth_details):
        self.auth_type = auth_type
        self.auth_details = auth_details
        self.client_id = auth_details.get('client_id')
        self.client_secret = auth_details.get('client_secret')

    @abstractmethod
    def build_token_request_headers(self):
        raise NotImplementedError(
            'Subclasses must implement build_token_request_headers'
        )


class BaseOAuth2ProviderAuthInterface(BaseProviderAuthInterface):
    AUTHORIZE_URL = None
    TOKEN_URL = None

    def build_token_request_headers(self):
        key = self.auth_details.get('token_header', 'Authorization')
        prefix = self.auth_details.get('token_prefix', 'Basic')
        if self.auth_details.get('use_basic_auth'):
            basic = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            return {key: f"{prefix} {basic}"}
        return {}

    @abstractmethod
    def get_authorize_url(self, **kwargs):
        raise NotImplementedError('Subclasses must implement get_authorize_url')

    @abstractmethod
    def handle_authorize_callback(self, **kwargs):
        raise NotImplementedError('Subclasses must implement handle_authorize_callback')

    def exchange_token(self, code, redirect_uri, extra_data=None, extra_headers=None):
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
        }
        if extra_data:
            data.update(extra_data)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        if extra_headers:
            headers.update(extra_headers)
        response = self.handle_request(
            'POST', self.TOKEN_URL, data=data, headers=headers
        )
        return response.json()

    def refresh_access_token(self, refresh_token, extra_data=None, extra_headers=None):
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        if extra_data:
            data.update(extra_data)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        if extra_headers:
            headers.update(extra_headers)
        response = self.handle_request(
            'POST', self.TOKEN_URL, data=data, headers=headers
        )
        return response.json()


class BaseJWTProviderAuthInterface(BaseProviderAuthInterface):
    def build_token_request_headers(self):
        payload = self.auth_details.get('jwt_payload') or {}
        secret = self.auth_details.get('jwt_secret') or self.client_secret
        algorithm = self.auth_details.get('jwt_algorithm', 'HS256')
        now = int(time.time())
        payload.setdefault('iat', now)
        payload.setdefault('exp', now + 3600)
        token = jwt.encode(payload, secret, algorithm=algorithm)
        key = self.auth_details.get('token_header', 'Authorization')
        prefix = self.auth_details.get('token_prefix', 'Bearer')
        return {key: f"{prefix} {token}"}


class BaseAPIProviderInterface(BaseHttpClient):
    def __init__(self, base_url, access_token):
        self.base_url = base_url.rstrip('/') + '/'
        self.access_token = access_token

    def build_request_headers(self, extra_headers=None):
        key = 'Authorization'
        prefix = 'Bearer'
        headers = {key: f"{prefix} {self.access_token}"}
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def build_url(self, endpoint):
        return f"{self.base_url}{endpoint.lstrip('/')}"

    def handle_request(self, method, endpoint, **kwargs):
        url = self.build_url(endpoint)
        headers = self.build_request_headers(kwargs.pop('headers', None))
        response = super().handle_request(method, url, headers=headers, **kwargs)
        return response.json()
