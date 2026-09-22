from io import StringIO

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase

from .roles import GUARD, RESIDENT, ROLE_PERMISSIONS, SOCIETY_ADMIN
from .testing import make_user


def permission_names(group):
    """A group's permissions as {'app_label.codename', ...}."""
    return {f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.all()}


def expected_names(role):
    return {f"{app_label}.{codename}" for app_label, codename in ROLE_PERMISSIONS[role]}


class SetupRolesCommandTests(TestCase):
    def run_command(self):
        output = StringIO()
        call_command("setup_roles", stdout=output)
        return output.getvalue()

    def test_creates_the_three_groups(self):
        output = self.run_command()
        self.assertEqual(
            sorted(Group.objects.values_list("name", flat=True)), [GUARD, RESIDENT, SOCIETY_ADMIN]
        )
        self.assertIn("Created group 'Guard' with 7 permissions.", output)
        self.assertIn("Roles are set up.", output)

    def test_each_group_has_exactly_its_listed_permissions(self):
        self.run_command()
        for role in [SOCIETY_ADMIN, GUARD, RESIDENT]:
            with self.subTest(role=role):
                self.assertEqual(permission_names(Group.objects.get(name=role)), expected_names(role))

    def test_no_role_can_delete_anything(self):
        self.run_command()
        for group in Group.objects.all():
            with self.subTest(group=group.name):
                self.assertFalse(any(".delete_" in name for name in permission_names(group)))

    def test_guard_cannot_manage_residents_or_users(self):
        self.run_command()
        guard = permission_names(Group.objects.get(name=GUARD))
        for forbidden in ["residents.view_resident", "residents.change_resident", "auth.change_user",
                          "society.change_flat", "vehicles.change_vehicle", "tracking.change_vehiclelog"]:
            with self.subTest(permission=forbidden):
                self.assertNotIn(forbidden, guard)

    def test_running_twice_is_safe_and_removes_extra_permissions(self):
        self.run_command()
        guard_group = Group.objects.get(name=GUARD)
        guard_group.permissions.add(Permission.objects.get(codename="delete_visitor"))

        output = self.run_command()

        self.assertEqual(Group.objects.count(), 3)
        self.assertIn("Updated group 'Guard' with 7 permissions.", output)
        self.assertEqual(permission_names(guard_group), expected_names(GUARD))


class MakeUserHelperTests(TestCase):
    def test_society_admin(self):
        user = make_user("admin")
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.has_perm("residents.change_resident"))
        self.assertTrue(user.has_perm("visitors.check_in_out_visitor"))
        self.assertFalse(user.has_perm("tracking.delete_vehiclelog"))

    def test_guard(self):
        user = make_user("guard")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.has_perm("tracking.add_vehiclelog"))
        self.assertTrue(user.has_perm("visitors.cancel_visitor"))
        self.assertTrue(user.has_perm("vehicles.view_vehicle"))
        self.assertFalse(user.has_perm("residents.view_resident"))
        self.assertFalse(user.has_perm("vehicles.change_vehicle"))

    def test_resident(self):
        user = make_user("resident")
        self.assertFalse(user.is_staff)
        self.assertEqual(user.get_all_permissions(), set())
        self.assertTrue(user.groups.filter(name=RESIDENT).exists())
