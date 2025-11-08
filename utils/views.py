from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from utils.renderers import WalrusRenderer
from utils.response import APISuccessResponse


class BaseAPIView(APIView):
    renderer_classes = [WalrusRenderer]


class BaseGenericViewSet(GenericViewSet):
    renderer_classes = [WalrusRenderer]


class HealthCheckView(BaseAPIView):
    """
    Health check endpoint to verify the service is running
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return APISuccessResponse(data={'service': 'walrus'})
