from django.urls import include, path
from rest_framework import routers

from account.views import LoginView, LogoutView, MemberViewSet, RefreshTokenView

app_name = 'account'

member_router = routers.DefaultRouter()


staff_router = routers.DefaultRouter()
staff_router.register(r'members', MemberViewSet, basename='member')


urlpatterns = [
    path('member/', include(member_router.urls)),
    path('staff/', include(staff_router.urls)),
    path('auth/login/', LoginView.as_view(), name='member_login'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
]
