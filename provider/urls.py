from django.urls import include, path
from rest_framework import routers

from provider.views import SpotifyAuthViewSet, SpotifyPlayLogViewSet

app_name = 'provider'

member_router = routers.DefaultRouter()

member_router.register(r'spotify-auth', SpotifyAuthViewSet, basename='spotify-auth')
# member_router.register(r'spotify', SpotifyAPIViewSet, basename='spotify-api')
member_router.register(
    r'spotify-playlog', SpotifyPlayLogViewSet, basename='spotify-playlog'
)

staff_router = routers.DefaultRouter()


urlpatterns = [
    path('member/', include(member_router.urls)),
]
