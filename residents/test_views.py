from django.test import TestCase
from django.urls import reverse

from society.models import Flat, Wing

from .models import Resident


class ResidentListPageTests(TestCase):
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
