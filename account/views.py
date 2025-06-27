from account.models import Member
from account.serializers import LoginSerializer
from account.utils.jwt import get_jwt_token_for_member
from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse, APISuccessResponse
from utils.views import BaseAPIView


class LoginView(BaseAPIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            # TODO: add member login cache
            member = Member.objects.get(email=email)
        except Member.DoesNotExist:
            return APIFailedResponse(
                code=ResponseCode.USER_NOT_FOUND,
                msg=ResponseMessage.USER_NOT_FOUND,
                details={
                    'email': email,
                },
            )

        jwt_tokens = get_jwt_token_for_member(member)
        return APISuccessResponse(data={'member_id': member.id, **jwt_tokens})
