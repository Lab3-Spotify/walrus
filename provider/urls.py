from django.urls import include, path
from rest_framework import routers

from provider.views import (
    GetSpotifyTokenView,
    SpotifyAuthViewSet,
    SpotifyPlayLogViewSet,
    SpotifyProxyAccountViewSet,
)

app_name = 'provider'

# OAuth ViewSet（member 和 proxy account 共用）
auth_router = routers.DefaultRouter()
auth_router.register(r'spotify-auth', SpotifyAuthViewSet, basename='spotify-auth')

# Member 專用
member_router = routers.DefaultRouter()
member_router.register(
    r'spotify-playlog', SpotifyPlayLogViewSet, basename='spotify-playlog'
)
member_router.register(
    r'proxy-account', SpotifyProxyAccountViewSet, basename='proxy-account'
)

staff_router = routers.DefaultRouter()


urlpatterns = [
    path('', include(auth_router.urls)),
    path('member/', include(member_router.urls)),
    path(
        'member/token/spotify/', GetSpotifyTokenView.as_view(), name='member-api-token'
    ),
]
