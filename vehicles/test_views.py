from django.test import TestCase
from accounts.testing import LoggedInAsSocietyAdminMixin
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing

from .models import Vehicle


class VehicleListPageTests(LoggedInAsSocietyAdminMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        wing_a = Wing.objects.create(name="A")
        wing_b = Wing.objects.create(name="B")
        rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing_a, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        priya = Resident.objects.create(
            flat=Flat.objects.create(wing=wing_b, flat_number="201"),
            full_name="Priya Patil",
            phone="9123456780",
        )
        Vehicle.objects.create(
            resident=rajesh,
            vehicle_number="MH12AB1234",
            vehicle_type=Vehicle.VehicleType.FOUR_WHEELER,
            model_name="Honda City",
            colour="White",
        )
        Vehicle.objects.create(
            resident=priya,
            vehicle_number="MH14CD5678",
            vehicle_type=Vehicle.VehicleType.TWO_WHEELER,
            model_name="Activa",
            colour="Grey",
            is_active=False,
        )

    def get_list(self, **params):
        return self.client.get(reverse("vehicles:vehicle_list"), params)

    def test_list_shows_vehicle_details(self):
        response = self.get_list()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "vehicles/vehicle_list.html")
        for text in ["MH12AB1234", "Four Wheeler", "Honda City", "White", "Rajesh Sharma",
                     "A-101", "MH14CD5678", "Two Wheeler", "Inactive"]:
            self.assertContains(response, text)

    def test_search_by_plate_typed_with_spaces(self):
        response = self.get_list(q="mh 12 ab")
        self.assertContains(response, "MH12AB1234")
        self.assertNotContains(response, "MH14CD5678")

    def test_search_by_owner_name(self):
        response = self.get_list(q="priya")
        self.assertContains(response, "MH14CD5678")
        self.assertNotContains(response, "MH12AB1234")

    def test_search_by_owner_flat(self):
        response = self.get_list(q="b-201")
        self.assertContains(response, "MH14CD5678")
        self.assertNotContains(response, "MH12AB1234")

    def test_filter_by_vehicle_type(self):
        response = self.get_list(type="TWO_WHEELER")
        self.assertContains(response, "MH14CD5678")
        self.assertNotContains(response, "MH12AB1234")

    def test_search_with_no_match_shows_message(self):
        response = self.get_list(q="zzz")
        self.assertContains(response, "No vehicles found")

    def test_navbar_links_to_vehicles_page(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, reverse("vehicles:vehicle_list"))
