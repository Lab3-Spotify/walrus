from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import AllowAny

from account.models import Member
from account.permissions import IsMember, IsStaff
from provider.exceptions import ProviderException
from provider.handlers.spotify import SpotifyAPIProviderHandler
from provider.models import MemberAPIToken, Provider, ProviderProxyAccount
from provider.serializers import ProviderProxyAccountSerializer
from provider.services import SpotifyProxyAccountService
from utils.constants import ResponseCode
from utils.redirect_service import RedirectService
from utils.response import APIFailedResponse, APISuccessResponse
from utils.utils import get_class_from_path
from utils.views import BaseAPIView, BaseGenericViewSet


class SpotifyAuthViewSet(BaseGenericViewSet):
    permission_classes = [IsMember | IsStaff]
    PROVIDER_PLATFORM = Provider.PlatformOptions.SPOTIFY

    def _get_auth_handler(self, provider):
        handler_path = provider.auth_handler
        return get_class_from_path(handler_path)(provider)

    @action(
        detail=False,
        methods=['get'],
        url_path='member/authorize',
        permission_classes=[IsMember],
    )
    def authorize_member(self, request):
        """Member OAuth 授權"""
        try:
            member = request.user.member
            provider = member.spotify_provider
            if not provider:
                raise ProviderException(
                    code=ResponseCode.NOT_FOUND,
                    message='No Spotify provider assigned to this member',
                )

            handler = self._get_auth_handler(provider)
            authorize_url = handler.get_authorize_url(
                request, state=member.id, account_type='member'
            )
            return APISuccessResponse(data=authorize_url)
        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)

    @action(
        detail=False,
        methods=['get'],
        url_path='member/authorize-callback',
        permission_classes=[AllowAny],
    )
    def authorize_member_callback(self, request):
        """Member OAuth callback"""
        try:
            state = request.GET.get('state')
            member = Member.objects.get(id=state)
            provider = member.spotify_provider

            if not provider:
                raise ProviderException(
                    code=ResponseCode.NOT_FOUND,
                    message='No Spotify provider assigned to this member',
                )

            handler = self._get_auth_handler(provider)
            result = handler.handle_authorize_callback(request, account_type='member')
            handler.process_token(result, member_id=member.id)

            return RedirectService.spotify_callback(status='success')
        except ProviderException:
            return RedirectService.spotify_callback(status='failed')

    @action(
        detail=False,
        methods=['get'],
        url_path='proxy-account/(?P<proxy_account_code>[^/.]+)/authorize',
        permission_classes=[IsStaff],
    )
    def authorize_proxy_account(self, request, proxy_account_code=None):
        """Proxy Account OAuth 授權（僅 Staff）"""
        try:
            proxy_account = ProviderProxyAccount.objects.select_related('provider').get(
                code=proxy_account_code
            )
            handler = self._get_auth_handler(proxy_account.provider)
            authorize_url = handler.get_authorize_url(
                request,
                state=proxy_account.id,  # state 還是用 id，因為 callback 要用
                account_type='proxy_account',
            )
            return APISuccessResponse(data=authorize_url)
        except ProviderProxyAccount.DoesNotExist:
            return APIFailedResponse(
                code=ResponseCode.NOT_FOUND, msg='Proxy account not found'
            )
        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)

    @action(
        detail=False,
        methods=['get'],
        url_path='proxy-account/authorize-callback',
        permission_classes=[AllowAny],
    )
    def authorize_proxy_account_callback(self, request):
        """Proxy Account OAuth callback"""
        try:
            state = request.GET.get('state')
            proxy_account = ProviderProxyAccount.objects.select_related('provider').get(
                id=state
            )

            handler = self._get_auth_handler(proxy_account.provider)
            result = handler.handle_authorize_callback(
                request, account_type='proxy_account'
            )
            handler.process_token(result, proxy_account_id=proxy_account.id)

            return APISuccessResponse()
        except ProviderProxyAccount.DoesNotExist:
            return APIFailedResponse(
                code=ResponseCode.NOT_FOUND, msg='Proxy account not found'
            )
        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)


class SpotifyPlayLogViewSet(viewsets.ViewSet):
    permission_classes = [IsMember | IsStaff]
    PROVIDER_PLATFORM = Provider.PlatformOptions.SPOTIFY

    @property
    def handler(self):
        member = self.request.user.member
        provider = member.spotify_provider

        if not provider:
            raise ProviderException(
                code=ResponseCode.NOT_FOUND,
                message='No Spotify provider assigned to this member',
            )

        handler_path = provider.api_handler
        return get_class_from_path(handler_path)(provider, member=member)

    @action(detail=False, methods=['post'], url_path='collect')
    def collect(self, request):
        try:
            played_logs = self.handler.collect_recently_played_logs(days=3)
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


class GetSpotifyTokenView(BaseAPIView):
    permission_classes = [IsMember | IsStaff]

    def get(self, request):
        member = request.user.member
        account_type = request.GET.get('account_type', 'member')

        if account_type == 'member':
            provider = member.spotify_provider
            if not provider:
                return APIFailedResponse(
                    code=ResponseCode.NOT_FOUND,
                    msg='No Spotify provider assigned to this member',
                )

            handler_path = provider.api_handler
            handler = get_class_from_path(handler_path)(provider, member=member)

        else:  # proxy_account
            proxy_account = member.proxy_accounts.filter(
                provider__platform=Provider.PlatformOptions.SPOTIFY
            ).first()

            if not proxy_account:
                return APIFailedResponse(
                    code=ResponseCode.NOT_FOUND,
                    msg='No proxy account assigned to this member',
                )

            handler_path = proxy_account.provider.api_handler
            handler = get_class_from_path(handler_path)(
                proxy_account.provider, proxy_account=proxy_account
            )

        try:
            access_token = handler.get_access_token()
            data = {
                'access_token': access_token,
            }

            return APISuccessResponse(data=data)
        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)


class SpotifyProxyAccountViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, BaseGenericViewSet
):
    permission_classes = [IsMember | IsStaff]
    queryset = ProviderProxyAccount.objects.all().select_related(
        'provider', 'current_member'
    )
    serializer_class = ProviderProxyAccountSerializer

    @action(detail=False, methods=['post'])
    def acquire(self, request):
        """分配 proxy account 給用戶"""
        member = request.user.member
        result = SpotifyProxyAccountService.acquire_proxy_account(member)

        if result.success:
            return APISuccessResponse(data=result.data)
        else:
            return APIFailedResponse(code=result.error_code, msg=result.message)

    @action(detail=False, methods=['post'])
    def release(self, request):
        """釋放用戶的 proxy account"""
        member = request.user.member
        result = SpotifyProxyAccountService.release_proxy_account(member)

        if result.success:
            return APISuccessResponse()
        else:
            return APIFailedResponse(code=result.error_code, msg=result.message)
