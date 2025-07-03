from django.utils.functional import cached_property
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from account.permissions import IsMember, IsStaff
from provider.exceptions import ProviderException
from provider.handlers.spotify import SpotifyAPIProviderHandler
from provider.models import Provider
from utils.response import APIFailedResponse, APISuccessResponse
from utils.utils import get_class_from_path
from walrus import settings


class SpotifyAuthViewSet(viewsets.ViewSet):
    permission_classes = [IsMember | IsStaff]
    PROVIDER_CODE = 'spotify'

    @cached_property
    def handler(self):
        provider = Provider.objects.get(code=self.PROVIDER_CODE)
        handler_path = provider.auth_handler
        return get_class_from_path(handler_path)(provider)

    @action(detail=False, methods=['get'], url_path='authorize')
    def authorize(self, request):
        try:
            authorize_url = self.handler.get_authorize_url(request)
            return APISuccessResponse(data=authorize_url)
        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)

    @action(
        detail=False,
        methods=['get'],
        url_path='authorize-callback',
        permission_classes=[AllowAny],
    )
    def authorize_callback(self, request):
        try:
            state = request.GET.get('state')
            result = self.handler.handle_authorize_callback(request)
            api_token = self.handler.process_token(
                request, {**result, 'member_id': state}
            )
            return APISuccessResponse(data=api_token)
        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)


class SpotifyPlayLogViewSet(viewsets.ViewSet):
    permission_classes = [IsMember | IsStaff]
    PROVIDER_CODE = 'spotify'

    @cached_property
    def handler(self):
        provider = Provider.objects.get(code=self.PROVIDER_CODE)
        return SpotifyAPIProviderHandler(provider, member=self.request.user.member)

    @action(detail=False, methods=['post'], url_path='collect')
    def collect(self, request):
        try:
            played_logs = self.handler.collect_recently_played_logs(days=1)
            data = [
                {
                    'track': pl.track.name,
                    'played_at': pl.played_at,
                }
                for pl in played_logs
            ]
            return APISuccessResponse(data=data)
        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)
