from django.utils.functional import cached_property
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from account.permissions import IsMember
from provider.exceptions import ProviderException
from provider.models import Provider
from utils.response import APIFailedResponse, APISuccessResponse
from utils.utils import get_class_from_path


class SpotifyAuthViewSet(viewsets.ViewSet):
    permission_classes = [IsMember]
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
