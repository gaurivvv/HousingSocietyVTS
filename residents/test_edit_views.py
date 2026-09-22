from django.test import TestCase
from accounts.testing import LoggedInAsSocietyAdminMixin
from django.urls import reverse

from society.models import Flat, Wing

from .models import Resident


class ResidentEditPageTests(LoggedInAsSocietyAdminMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.flat_101 = Flat.objects.create(wing=wing, flat_number="101")
        cls.flat_102 = Flat.objects.create(wing=wing, flat_number="102")
        cls.rajesh = Resident.objects.create(
            flat=cls.flat_101, full_name="Rajesh Sharma", phone="9876543210"
        )
        cls.priya = Resident.objects.create(
            flat=cls.flat_101,
            full_name="Priya Sharma",
            phone="9123456780",
            resident_type=Resident.ResidentType.TENANT,
        )

    def edit_url(self, resident):
        return reverse("residents:resident_update", args=[resident.pk])

    def form_data(self, **changes):
        # Rajesh's current details; each test changes only what it checks
        data = {
            "flat": str(self.flat_101.pk),
            "full_name": "Rajesh Sharma",
            "resident_type": "OWNER",
            "phone": "9876543210",
            "email": "",
        }
        data.update(changes)
        return data

    def test_edit_page_shows_current_values(self):
        response = self.client.get(self.edit_url(self.rajesh))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "residents/resident_form.html")
        self.assertContains(response, "Edit Resident")
        self.assertContains(response, 'value="Rajesh Sharma"')
        self.assertContains(response, 'value="9876543210"')

    def test_list_page_links_to_edit_page(self):
        response = self.client.get(reverse("residents:resident_list"))
        self.assertContains(response, self.edit_url(self.rajesh))

    def test_update_saves_changes_and_shows_message(self):
        response = self.client.post(
            self.edit_url(self.rajesh),
            self.form_data(
                flat=str(self.flat_102.pk), resident_type="TENANT", email="Rajesh@Example.com"
            ),
            follow=True,
        )
        self.assertRedirects(response, reverse("residents:resident_list"))
        self.assertContains(response, "Resident Rajesh Sharma was updated.")
        self.rajesh.refresh_from_db()
        self.assertEqual(self.rajesh.flat, self.flat_102)
        self.assertEqual(self.rajesh.resident_type, "TENANT")
        self.assertEqual(self.rajesh.email, "rajesh@example.com")
        self.assertEqual(Resident.objects.count(), 2)  # updated, not duplicated

    def test_saving_without_changes_is_not_a_duplicate(self):
        response = self.client.post(self.edit_url(self.rajesh), self.form_data())
        self.assertEqual(response.status_code, 302)

    def test_cannot_rename_to_another_resident_in_same_flat(self):
        response = self.client.post(self.edit_url(self.rajesh), self.form_data(full_name="priya sharma"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already recorded for flat A-101")
        self.rajesh.refresh_from_db()
        self.assertEqual(self.rajesh.full_name, "Rajesh Sharma")

    def test_invalid_phone_keeps_old_value(self):
        response = self.client.post(self.edit_url(self.rajesh), self.form_data(phone="123"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")
        self.rajesh.refresh_from_db()
        self.assertEqual(self.rajesh.phone, "9876543210")

    def test_missing_resident_returns_404(self):
        response = self.client.get(reverse("residents:resident_update", args=[99999]))
        self.assertEqual(response.status_code, 404)
