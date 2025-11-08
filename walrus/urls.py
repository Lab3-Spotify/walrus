"""
URL configuration for walrus project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from utils.views import HealthCheckView
from walrus import settings

urlpatterns = [
    path('ivory/', admin.site.urls),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
    path('api/account/', include(('account.urls', 'account'), namespace='account')),
    path('api/provider/', include(('provider.urls', 'provider'), namespace='provider')),
    path('api/playlist/', include(('playlist.urls', 'playlist'), namespace='playlist')),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Spotify OAuth2 requires that, when using http (local development), the redirect_uri
# must be as simple as possible, e.g., http://127.0.0.1:8000/callback/member/ (no subpaths allowed).
if settings.ENV == 'local':
    from django.http import Http404
    from rest_framework.permissions import AllowAny

    from provider.views import SpotifyAuthViewSet

    class LocalhostOnlySpotifyAuthCallbackView(SpotifyAuthViewSet):
        permission_classes = [AllowAny]

        def _check_localhost(self, request):
            if request.get_host().split(':')[0] != '127.0.0.1':
                raise Http404()

        def authorize_member_callback(self, request, *args, **kwargs):
            self._check_localhost(request)
            return super().authorize_member_callback(request, *args, **kwargs)

        def authorize_proxy_account_callback(self, request, *args, **kwargs):
            self._check_localhost(request)
            return super().authorize_proxy_account_callback(request, *args, **kwargs)

    test_urlpatterns = [
        path(
            'callback/member/',
            LocalhostOnlySpotifyAuthCallbackView.as_view(
                {'get': 'authorize_member_callback'}
            ),
            name='root-callback-member',
        ),
        path(
            'callback/proxy-account/',
            LocalhostOnlySpotifyAuthCallbackView.as_view(
                {'get': 'authorize_proxy_account_callback'}
            ),
            name='root-callback-proxy-account',
        ),
    ]

    urlpatterns += test_urlpatterns
