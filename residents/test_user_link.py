from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.testing import TEST_PASSWORD, LoggedInAsSocietyAdminMixin
from society.models import Flat, Wing

from .forms import ResidentForm
from .models import Resident

WEBSITE_FORM_FIELDS = {"flat", "full_name", "resident_type", "phone", "email"}


class ResidentUserLinkModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flat = Flat.objects.create(wing=Wing.objects.create(name="A"), flat_number="101")

    def make_resident(self, name="Rajesh Sharma", phone="9876543210", **fields):
        return Resident.objects.create(flat=self.flat, full_name=name, phone=phone, **fields)

    def make_login(self, username="rajesh_login"):
        return User.objects.create_user(username=username, password=TEST_PASSWORD)

    def test_resident_can_be_created_without_a_user(self):
        resident = self.make_resident()
        resident.full_clean()  # the field is optional: no validation error
        resident.refresh_from_db()
        self.assertIsNone(resident.user)

    def test_link_works_in_both_directions(self):
        login = self.make_login()
        resident = self.make_resident(user=login)
        login.refresh_from_db()
        self.assertEqual(resident.user, login)
        self.assertEqual(login.resident, resident)

    def test_one_user_cannot_be_linked_to_two_residents(self):
        login = self.make_login()
        self.make_resident(user=login)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_resident(name="Priya Sharma", phone="9123456780", user=login)

    def test_deleting_the_user_keeps_the_resident_unlinked(self):
        login = self.make_login()
        resident = self.make_resident(user=login)
        login.delete()
        resident.refresh_from_db()
        self.assertIsNone(resident.user)
        self.assertEqual(resident.full_name, "Rajesh Sharma")

    def test_unlinked_user_can_be_checked_safely(self):
        login = self.make_login()
        # Django's own behaviour: no error, just "no linked resident"
        self.assertFalse(hasattr(login, "resident"))
        self.assertIsNone(getattr(login, "resident", None))


class ResidentWebsiteFormDoesNotExposeUserTests(LoggedInAsSocietyAdminMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flat = Flat.objects.create(wing=Wing.objects.create(name="A"), flat_number="101")
        cls.linked_login = User.objects.create_user(username="linked_login", password=TEST_PASSWORD)
        cls.other_login = User.objects.create_user(username="other_login", password=TEST_PASSWORD)
        cls.linked_resident = Resident.objects.create(
            flat=cls.flat, full_name="Rajesh Sharma", phone="9876543210", user=cls.linked_login
        )

    def form_data(self, **changes):
        data = {"flat": self.flat.pk, "full_name": "Amit Kulkarni", "resident_type": "OWNER",
                "phone": "9988776655", "email": ""}
        data.update(changes)
        return data

    def test_website_form_fields_are_unchanged(self):
        self.assertEqual(set(ResidentForm().fields), WEBSITE_FORM_FIELDS)

    def test_add_page_has_no_user_input(self):
        response = self.client.get(reverse("residents:resident_create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="user"')

    def test_edit_page_has_no_user_input(self):
        response = self.client.get(reverse("residents:resident_update", args=[self.linked_resident.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="user"')

    def test_extra_user_value_on_add_is_ignored(self):
        response = self.client.post(reverse("residents:resident_create"), self.form_data(user=self.other_login.pk))
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Resident.objects.get(full_name="Amit Kulkarni").user)

    def test_editing_a_linked_resident_keeps_the_link(self):
        response = self.client.post(
            reverse("residents:resident_update", args=[self.linked_resident.pk]),
            self.form_data(full_name="Rajesh Kumar Sharma", phone="9876543210"),
        )
        self.assertEqual(response.status_code, 302)
        self.linked_resident.refresh_from_db()
        self.assertEqual(self.linked_resident.full_name, "Rajesh Kumar Sharma")
        self.assertEqual(self.linked_resident.user, self.linked_login)
