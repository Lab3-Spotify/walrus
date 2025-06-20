from rest_framework_simplejwt.tokens import RefreshToken


def get_jwt_token_for_member(member):
    refresh = RefreshToken.for_user(member.user)

    refresh['member_id'] = member.id
    refresh['email'] = member.email
    refresh['experiment_group'] = member.experiment_group
    refresh['name'] = member.name
    refresh['role'] = member.role

    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
    }
