from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle


class HomePageTests(TestCase):
    def test_home_page_loads_on_an_empty_database(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "dashboard/home.html")
        self.assertContains(response, "Society Overview")
        self.assertEqual(response.context["wing_count"], 0)

    def test_home_page_counts_only_active_residents_and_vehicles(self):
        wing = Wing.objects.create(name="A")
        flat = Flat.objects.create(wing=wing, flat_number="101")
        active = Resident.objects.create(flat=flat, full_name="Rajesh Sharma", phone="9876543210")
        Resident.objects.create(
            flat=flat, full_name="Old Tenant", phone="9123456780", is_active=False
        )
        Vehicle.objects.create(resident=active, vehicle_number="MH12AB1234")
        Vehicle.objects.create(resident=active, vehicle_number="MH12CD5678", is_active=False)

        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["wing_count"], 1)
        self.assertEqual(response.context["flat_count"], 1)
        self.assertEqual(response.context["active_resident_count"], 1)
        self.assertEqual(response.context["active_vehicle_count"], 1)
