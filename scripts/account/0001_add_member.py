from account.models import ExperimentGroup, Member
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        # Get ExperimentGroups
        groups = {
            group.code: group
            for group in ExperimentGroup.objects.filter(
                code__in=['SE', 'SM', 'LE', 'LM']
            )
        }

        members_data = {
            'pony@se.com': {
                'name': 'pony_se',
                'experiment_group': groups['SE'],
                'role': Member.RoleOptions.MEMBER,
            },
            'pony@sm.com': {
                'name': 'pony_sm',
                'experiment_group': groups['SM'],
                'role': Member.RoleOptions.MEMBER,
            },
            'pony@le.com': {
                'name': 'pony_le',
                'experiment_group': groups['LE'],
                'role': Member.RoleOptions.MEMBER,
            },
            'pony@lm.com': {
                'name': 'pony_lm',
                'experiment_group': groups['LM'],
                'role': Member.RoleOptions.MEMBER,
            },
            'pony@staff.com': {
                'name': 'pony_staff',
                'experiment_group': None,
                'role': Member.RoleOptions.STAFF,
            },
        }

        for email, data in members_data.items():
            if Member.objects.filter(email=email).exists():
                continue

            Member.objects.create(
                email=email,
                name=data['name'],
                experiment_group=data['experiment_group'],
                role=data['role'],
            )
