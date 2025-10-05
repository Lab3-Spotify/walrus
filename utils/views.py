from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from utils.renderers import WalrusRenderer


class BaseAPIView(APIView):
    renderer_classes = [WalrusRenderer]


class BaseGenericViewSet(GenericViewSet):
    renderer_classes = [WalrusRenderer]
