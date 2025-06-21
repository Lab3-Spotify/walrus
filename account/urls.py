from django.urls import include, path
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView

from account.views import LoginView

member_router = routers.DefaultRouter()


staff_router = routers.DefaultRouter()


urlpatterns = [
    path('member/', include(member_router.urls)),
    path('staff/', include(staff_router.urls)),
    path('login/', LoginView.as_view(), name='member_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
