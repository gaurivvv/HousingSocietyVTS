from datetime import timedelta

from django.test import TestCase
from accounts.testing import LoggedInAsSocietyAdminMixin
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle


class HomePageTests(LoggedInAsSocietyAdminMixin, TestCase):
    def test_home_page_loads_on_an_empty_database(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "dashboard/home.html")
        self.assertContains(response, "Society Overview")
        self.assertEqual(response.context["wing_count"], 0)
        self.assertEqual(response.context["inside_count"], 0)

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

    def test_home_page_shows_gate_activity(self):
        now = timezone.now()
        # KA01AA0001 entered and is still inside; KA01BB0002 entered and left
        VehicleLog.objects.create(plate_number="KA01AA0001", movement_type="ENTRY", timestamp=now - timedelta(minutes=3))
        VehicleLog.objects.create(plate_number="KA01BB0002", movement_type="ENTRY", timestamp=now - timedelta(minutes=2))
        VehicleLog.objects.create(plate_number="KA01BB0002", movement_type="EXIT", timestamp=now - timedelta(minutes=1))

        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Gate activity")
        self.assertEqual(response.context["inside_count"], 1)
        self.assertEqual(response.context["todays_entries"], 2)
        self.assertEqual(response.context["todays_exits"], 1)

    def test_home_page_has_quick_links_to_management_pages(self):
        response = self.client.get(reverse("dashboard:home"))
        for url_name in [
            "tracking:gate",
            "residents:resident_list",
            "residents:resident_create",
            "vehicles:vehicle_list",
            "vehicles:vehicle_create",
        ]:
            self.assertContains(response, reverse(url_name))
        self.assertNotContains(response, "being built next")
