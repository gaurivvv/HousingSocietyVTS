from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.roles import ROLE_PERMISSIONS


class Command(BaseCommand):
    help = "Create or update the Society Admin, Guard and Resident groups with exactly their listed permissions."

    @transaction.atomic
    def handle(self, *args, **options):
        for role, wanted in ROLE_PERMISSIONS.items():
            permissions = []
            for app_label, codename in wanted:
                try:
                    permissions.append(
                        Permission.objects.get(content_type__app_label=app_label, codename=codename)
                    )
                except Permission.DoesNotExist:
                    raise CommandError(
                        f"Permission {app_label}.{codename} does not exist. Run 'python manage.py migrate' first."
                    )

            group, created = Group.objects.get_or_create(name=role)
            # set() adds missing permissions and removes any extra ones
            group.permissions.set(permissions)

            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} group '{role}' with {len(permissions)} permissions.")

        self.stdout.write(self.style.SUCCESS("Roles are set up."))
