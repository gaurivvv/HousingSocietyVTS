from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from society.models import Flat, Wing

from .models import Resident


class ResidentAdminTests(TestCase):
    """Uses the Resident admin pages the same way a person would in the browser."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="testadmin", password="Test-admin-pass-2026"
        )
        cls.wing_a = Wing.objects.create(name="A")
        cls.wing_b = Wing.objects.create(name="B")
        cls.flat_a101 = Flat.objects.create(wing=cls.wing_a, flat_number="101")
        cls.flat_b201 = Flat.objects.create(wing=cls.wing_b, flat_number="201")

    def setUp(self):
        self.client.force_login(self.admin_user)

    def resident_form_data(self, **changes):
        data = {
            "flat": str(self.flat_a101.pk),
            "full_name": "Rajesh Sharma",
            "resident_type": "OWNER",
            "phone": "9876543210",
            "email": "",
            "is_active": "on",
        }
        data.update(changes)
        return data

    def test_add_resident_tidies_name_and_email(self):
        response = self.client.post(
            reverse("admin:residents_resident_add"),
            self.resident_form_data(full_name="  Rajesh   Sharma ", email="Rajesh@Example.COM"),
        )
        self.assertEqual(response.status_code, 302)
        resident = Resident.objects.get()
        self.assertEqual(resident.full_name, "Rajesh Sharma")
        self.assertEqual(resident.email, "rajesh@example.com")
        self.assertEqual(resident.flat, self.flat_a101)

    def test_invalid_phone_is_rejected(self):
        response = self.client.post(
            reverse("admin:residents_resident_add"),
            self.resident_form_data(phone="12345"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid 10-digit Indian mobile number")
        self.assertEqual(Resident.objects.count(), 0)

    def test_list_search_and_wing_filter(self):
        Resident.objects.create(flat=self.flat_a101, full_name="Rajesh Sharma", phone="9876543210")
        Resident.objects.create(flat=self.flat_b201, full_name="Priya Patil", phone="9123456780")
        list_url = reverse("admin:residents_resident_changelist")

        response = self.client.get(list_url, {"q": "rajesh"})
        self.assertContains(response, "Rajesh Sharma")
        self.assertNotContains(response, "Priya Patil")

        response = self.client.get(list_url, {"flat__wing__id__exact": self.wing_b.pk})
        self.assertContains(response, "Priya Patil")
        self.assertNotContains(response, "Rajesh Sharma")

    def test_mark_inactive_action(self):
        resident = Resident.objects.create(
            flat=self.flat_a101, full_name="Rajesh Sharma", phone="9876543210"
        )
        response = self.client.post(
            reverse("admin:residents_resident_changelist"),
            {"action": "mark_inactive", "_selected_action": [resident.pk]},
        )
        self.assertEqual(response.status_code, 302)
        resident.refresh_from_db()
        self.assertFalse(resident.is_active)

    def test_flat_with_residents_cannot_be_deleted(self):
        Resident.objects.create(flat=self.flat_a101, full_name="Rajesh Sharma", phone="9876543210")
        response = self.client.post(
            reverse("admin:society_flat_changelist"),
            {"action": "delete_selected", "_selected_action": [self.flat_a101.pk], "post": "yes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "protected")
        self.assertTrue(Flat.objects.filter(pk=self.flat_a101.pk).exists())