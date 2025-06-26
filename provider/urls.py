from django.urls import include, path
from rest_framework import routers

from provider.views import SpotifyAuthViewSet

app_name = 'provider'

member_router = routers.DefaultRouter()

member_router.register(r'spotify-auth', SpotifyAuthViewSet, basename='spotify_auth')

staff_router = routers.DefaultRouter()


urlpatterns = [
    path('member/', include(member_router.urls)),
]
