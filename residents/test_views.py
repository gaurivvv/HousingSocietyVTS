from django.test import TestCase
from accounts.testing import LoggedInAsSocietyAdminMixin
from django.urls import reverse

from society.models import Flat, Wing

from .models import Resident


class ResidentListPageTests(LoggedInAsSocietyAdminMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        wing_a = Wing.objects.create(name="A")
        wing_b = Wing.objects.create(name="B")
        Resident.objects.create(
            flat=Flat.objects.create(wing=wing_a, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
            email="rajesh@example.com",
        )
        Resident.objects.create(
            flat=Flat.objects.create(wing=wing_b, flat_number="201"),
            full_name="Priya Patil",
            phone="9123456780",
            resident_type=Resident.ResidentType.TENANT,
            is_active=False,
        )

    def get_list(self, **params):
        return self.client.get(reverse("residents:resident_list"), params)

    def test_list_shows_resident_details(self):
        response = self.get_list()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "residents/resident_list.html")
        for text in ["Rajesh Sharma", "A-101", "Owner", "9876543210",
                     "rajesh@example.com", "Priya Patil", "Tenant", "Inactive"]:
            self.assertContains(response, text)

    def test_search_by_name(self):
        response = self.get_list(q="rajesh")
        self.assertContains(response, "Rajesh Sharma")
        self.assertNotContains(response, "Priya Patil")

    def test_search_by_phone(self):
        response = self.get_list(q="91234")
        self.assertContains(response, "Priya Patil")
        self.assertNotContains(response, "Rajesh Sharma")

    def test_search_by_flat_number(self):
        response = self.get_list(q="201")
        self.assertContains(response, "Priya Patil")
        self.assertNotContains(response, "Rajesh Sharma")

    def test_search_by_wing_and_flat(self):
        response = self.get_list(q="a-101")
        self.assertContains(response, "Rajesh Sharma")
        self.assertNotContains(response, "Priya Patil")

    def test_search_with_no_match_shows_message(self):
        response = self.get_list(q="zzz")
        self.assertContains(response, "No residents found")

    def test_navbar_links_to_residents_page(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, reverse("residents:resident_list"))


class ResidentCreatePageTests(LoggedInAsSocietyAdminMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.flat_101 = Flat.objects.create(wing=wing, flat_number="101")
        cls.flat_102 = Flat.objects.create(wing=wing, flat_number="102")

    def form_data(self, **changes):
        data = {
            "flat": str(self.flat_101.pk),
            "full_name": "Amit Kulkarni",
            "resident_type": "OWNER",
            "phone": "9988776655",
            "email": "",
        }
        data.update(changes)
        return data

    def post_form(self, **changes):
        return self.client.post(reverse("residents:resident_create"), self.form_data(**changes))

    def test_add_page_loads_and_list_links_to_it(self):
        response = self.client.get(reverse("residents:resident_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "residents/resident_form.html")
        list_page = self.client.get(reverse("residents:resident_list"))
        self.assertContains(list_page, reverse("residents:resident_create"))

    def test_valid_form_creates_resident_and_shows_message(self):
        response = self.client.post(
            reverse("residents:resident_create"),
            self.form_data(
                full_name="  Amit   Kulkarni ",
                phone="+91 99887 76655",
                email="Amit@Example.COM",
            ),
            follow=True,
        )
        self.assertRedirects(response, reverse("residents:resident_list"))
        self.assertContains(response, "Resident Amit Kulkarni was added.")
        resident = Resident.objects.get()
        self.assertEqual(resident.full_name, "Amit Kulkarni")
        self.assertEqual(resident.phone, "9988776655")
        self.assertEqual(resident.email, "amit@example.com")
        self.assertTrue(resident.is_active)

    def test_invalid_phone_is_rejected(self):
        response = self.post_form(phone="12345")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")
        self.assertEqual(Resident.objects.count(), 0)

    def test_name_with_numbers_is_rejected(self):
        response = self.post_form(full_name="Amit 123")
        self.assertContains(response, "Name should not contain numbers.")
        self.assertEqual(Resident.objects.count(), 0)

    def test_duplicate_name_in_same_flat_is_rejected(self):
        Resident.objects.create(flat=self.flat_101, full_name="Amit Kulkarni", phone="9988776655")
        response = self.post_form(full_name="amit kulkarni")
        self.assertContains(response, "already recorded for flat A-101")
        self.assertEqual(Resident.objects.count(), 1)

    def test_same_name_in_different_flat_is_allowed(self):
        Resident.objects.create(flat=self.flat_101, full_name="Amit Kulkarni", phone="9988776655")
        response = self.post_form(flat=str(self.flat_102.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Resident.objects.count(), 2)

    def test_empty_form_shows_required_errors(self):
        response = self.client.post(reverse("residents:resident_create"), {})
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        for field in ["flat", "full_name", "phone"]:
            self.assertIn(field, form.errors)
        self.assertEqual(Resident.objects.count(), 0)
