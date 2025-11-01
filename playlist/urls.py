from django.urls import include, path
from rest_framework import routers

from playlist.views import PlaylistViewSet

app_name = 'playlist'

# Member 專用
member_router = routers.DefaultRouter()
member_router.register(r'', PlaylistViewSet, basename='playlist')

urlpatterns = [
    path('member/', include(member_router.urls)),
]
