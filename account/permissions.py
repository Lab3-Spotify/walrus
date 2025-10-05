from rest_framework.permissions import BasePermission

from account.models import Member


class IsMember(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user
            and user.is_authenticated
            and hasattr(user, 'member')
            and user.member.role == Member.RoleOptions.MEMBER
        )


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user
            and user.is_authenticated
            and hasattr(user, 'member')
            and user.member.role == Member.RoleOptions.STAFF
        )
