from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from utils.mixins import ResponseFormatMixin


class BaseAPIView(ResponseFormatMixin, APIView):
    pass


class BaseGenericViewSet(ResponseFormatMixin, GenericViewSet):
    pass
