from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from accounts.testing import TEST_PASSWORD
from society.models import Flat, Wing

from .models import Resident
from .utils import get_linked_resident


class GetLinkedResidentTests(TestCase):
    """Rajesh and Priya each have their own login; a third login is not linked to anyone."""

    @classmethod
    def setUpTestData(cls):
        flat = Flat.objects.create(wing=Wing.objects.create(name="A"), flat_number="101")
        cls.rajesh_login = User.objects.create_user(username="rajesh_login", password=TEST_PASSWORD)
        cls.priya_login = User.objects.create_user(username="priya_login", password=TEST_PASSWORD)
        cls.rajesh = Resident.objects.create(
            flat=flat, full_name="Rajesh Sharma", phone="9876543210",
            email="rajesh@example.com", user=cls.rajesh_login,
        )
        cls.priya = Resident.objects.create(
            flat=flat, full_name="Priya Patil", phone="9123456780", user=cls.priya_login,
        )
        # Same email as Rajesh and a similar username, but NOT linked: must not be matched
        cls.unlinked_login = User.objects.create_user(
            username="rajesh", email="rajesh@example.com", password=TEST_PASSWORD
        )

    def fresh(self, login):
        """Reload the login, so nothing cached from earlier lookups is reused."""
        return User.objects.get(pk=login.pk)

    def test_linked_user_returns_their_resident(self):
        self.assertEqual(get_linked_resident(self.fresh(self.rajesh_login)), self.rajesh)

    def test_unlinked_user_returns_none(self):
        self.assertIsNone(get_linked_resident(self.fresh(self.unlinked_login)))

    def test_anonymous_user_returns_none(self):
        self.assertIsNone(get_linked_resident(AnonymousUser()))

    def test_none_returns_none(self):
        self.assertIsNone(get_linked_resident(None))

    def test_each_user_gets_only_their_own_resident(self):
        self.assertEqual(get_linked_resident(self.fresh(self.rajesh_login)), self.rajesh)
        self.assertEqual(get_linked_resident(self.fresh(self.priya_login)), self.priya)
        self.assertNotEqual(get_linked_resident(self.fresh(self.priya_login)), self.rajesh)

    def test_no_guessing_from_matching_username_or_email(self):
        # This login shares Rajesh's email and resembles his name, but has no link
        self.assertIsNone(get_linked_resident(self.fresh(self.unlinked_login)))

    def test_inactive_resident_is_still_returned(self):
        Resident.objects.filter(pk=self.rajesh.pk).update(is_active=False)
        resident = get_linked_resident(self.fresh(self.rajesh_login))
        self.assertEqual(resident, self.rajesh)
        self.assertFalse(resident.is_active)
