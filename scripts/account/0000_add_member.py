from django.contrib.auth.models import User

from account.models import Member
from scripts.base import BaseScript
from walrus import settings


class CustomScript(BaseScript):
    def run(self):
        members_d = {
            'testuser@example.com': {
                'name': 'Test User 1',
                'experiment_group': Member.EXPERIMENT_GROUP_LONG,
                'role': Member.ROLE_MEMBER,
            },
            'testuser2@example.com': {
                'name': 'Test User 2',
                'experiment_group': Member.EXPERIMENT_GROUP_SHORT,
                'role': Member.ROLE_MEMBER,
            },
            'testuser3@example.com': {
                'name': 'Test User 3',
                'experiment_group': Member.EXPERIMENT_GROUP_LONG,
                'role': Member.ROLE_MEMBER,
            },
            'testuser4@example.com': {
                'name': 'Test User 4',
                'experiment_group': Member.EXPERIMENT_GROUP_SHORT,
                'role': Member.ROLE_MEMBER,
            },
            'testuser5@example.com': {
                'name': 'Test User 5',
                'experiment_group': Member.EXPERIMENT_GROUP_LONG,
                'role': Member.ROLE_MEMBER,
            },
            'pony@long.com': {
                'name': 'pony_long',
                'experiment_group': Member.EXPERIMENT_GROUP_LONG,
                'role': Member.ROLE_MEMBER,
            },
            'pony@short.com': {
                'name': 'pony_short',
                'experiment_group': Member.EXPERIMENT_GROUP_SHORT,
                'role': Member.ROLE_MEMBER,
            },
            'pony@staff.com': {
                'name': 'pony_staff',
                'experiment_group': Member.EXPERIMENT_GROUP_LONG,
                'role': Member.ROLE_STAFF,
            },
        }

        members = []
        for email, data in members_d.items():
            user, created = User.objects.get_or_create(
                username=email,
                defaults={
                    'email': email,
                    'first_name': data['name'],
                    'password': settings.DEFAULT_MEMBER_PASSWORD,
                },
            )
            member = Member(
                user=user,
                name=data['name'],
                experiment_group=data['experiment_group'],
                role=data['role'],
                email=email,
            )
            members.append(member)
        Member.objects.bulk_create(members, ignore_conflicts=True)
