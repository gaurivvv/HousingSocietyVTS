"""Helpers for tests: create a user in one of the three roles, or log the test client in."""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command

from .roles import GUARD, RESIDENT, SOCIETY_ADMIN

ROLE_NAMES = {"admin": SOCIETY_ADMIN, "guard": GUARD, "resident": RESIDENT}
TEST_PASSWORD = "Test-pass-2026!"


def make_user(role, username=None):
    """Create an active user in the given role: 'admin', 'guard' or 'resident'.

    Society Admins also get is_staff=True (Django Admin access); the others do not.
    """
    call_command("setup_roles", stdout=StringIO())  # make sure the groups exist
    user = User.objects.create_user(
        username=username or f"test_{role}",
        password=TEST_PASSWORD,
        is_staff=(role == "admin"),
    )
    user.groups.add(Group.objects.get(name=ROLE_NAMES[role]))
    return user


class LoggedInAsSocietyAdminMixin:
    """For page tests: log the test client in as a Society Admin before each test.

    Put it first in the class line, before TestCase, for example:
        class GatePageTests(LoggedInAsSocietyAdminMixin, TestCase):
    """

    def setUp(self):
        super().setUp()
        self.page_test_user = make_user("admin", username="page_test_admin")
        self.client.force_login(self.page_test_user)
