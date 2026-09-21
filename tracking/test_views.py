from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle

from .models import VehicleLog


class GatePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        cls.car = Vehicle.objects.create(resident=cls.rajesh, vehicle_number="MH12AB1234")

    def record(self, follow=False, **changes):
        data = {
            "plate_number": "MH12AB1234",
            "movement_type": "ENTRY",
            "category": "UNKNOWN",
            "remarks": "",
        }
        data.update(changes)
        return self.client.post(reverse("tracking:gate"), data, follow=follow)

    def test_gate_page_loads_and_navbar_links_to_it(self):
        response = self.client.get(reverse("tracking:gate"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tracking/gate.html")
        self.assertContains(response, "No gate movements recorded yet.")
        home = self.client.get(reverse("dashboard:home"))
        self.assertContains(home, reverse("tracking:gate"))

    def test_guard_cannot_choose_registered(self):
        response = self.client.get(reverse("tracking:gate"))
        choices = [value for value, label in response.context["form"].fields["category"].choices]
        self.assertEqual(choices, ["UNKNOWN", "VISITOR"])

        response = self.record(category="REGISTERED")
        self.assertEqual(response.status_code, 200)
        self.assertIn("category", response.context["form"].errors)
        self.assertEqual(VehicleLog.objects.count(), 0)

    def test_registered_vehicle_entry(self):
        response = self.record(follow=True, plate_number="mh 12 ab 1234")
        self.assertRedirects(response, reverse("tracking:gate"))
        self.assertContains(
            response, "Entry recorded for MH12AB1234: registered vehicle of Rajesh Sharma (A-101)."
        )
        log = VehicleLog.objects.get()
        self.assertEqual(log.vehicle, self.car)
        self.assertEqual(log.category, VehicleLog.Category.REGISTERED)

    def test_unknown_vehicle_entry_shows_warning(self):
        response = self.record(follow=True, plate_number="KA01XY0001")
        self.assertContains(response, "Entry recorded for KA01XY0001: unknown vehicle.")
        self.assertContains(response, "alert-warning")
        log = VehicleLog.objects.get()
        self.assertIsNone(log.vehicle)
        self.assertEqual(log.category, VehicleLog.Category.UNKNOWN)

    def test_visitor_vehicle_exit(self):
        response = self.record(
            follow=True, plate_number="GJ05AB1111", movement_type="EXIT", category="VISITOR",
            remarks="Visiting A-101",
        )
        self.assertContains(response, "Exit recorded for GJ05AB1111: visitor vehicle.")
        log = VehicleLog.objects.get()
        self.assertEqual(log.movement_type, VehicleLog.MovementType.EXIT)
        self.assertEqual(log.category, VehicleLog.Category.VISITOR)
        self.assertEqual(log.remarks, "Visiting A-101")

    def test_recent_movements_show_owner_and_badges(self):
        self.record(plate_number="MH12AB1234")
        self.record(plate_number="KA01XY0001")
        response = self.client.get(reverse("tracking:gate"))
        for text in ["MH12AB1234", "KA01XY0001", "Rajesh Sharma", "Registered", "Unknown"]:
            self.assertContains(response, text)

    def test_empty_form_shows_required_errors(self):
        response = self.client.post(reverse("tracking:gate"), {})
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        for field in ["plate_number", "movement_type"]:
            self.assertIn(field, form.errors)
        self.assertEqual(VehicleLog.objects.count(), 0)

    def test_too_short_plate_is_rejected(self):
        response = self.record(plate_number="AB")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter the full vehicle number seen at the gate.")
        self.assertEqual(VehicleLog.objects.count(), 0)
