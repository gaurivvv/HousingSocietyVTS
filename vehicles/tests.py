from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing

from .models import Vehicle


class VehicleAdminTests(TestCase):
    """Uses the Vehicle admin pages the same way a person would in the browser."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="testadmin", password="Test-admin-pass-2026"
        )
        wing_a = Wing.objects.create(name="A")
        cls.wing_b = Wing.objects.create(name="B")
        cls.rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing_a, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        cls.priya = Resident.objects.create(
            flat=Flat.objects.create(wing=cls.wing_b, flat_number="201"),
            full_name="Priya Patil",
            phone="9123456780",
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def vehicle_form_data(self, **changes):
        data = {
            "resident": str(self.rajesh.pk),
            "vehicle_number": "MH12AB1234",
            "vehicle_type": "FOUR_WHEELER",
            "model_name": "",
            "colour": "",
            "is_active": "on",
        }
        data.update(changes)
        return data

    def test_add_vehicle_normalizes_plate(self):
        response = self.client.post(
            reverse("admin:vehicles_vehicle_add"),
            self.vehicle_form_data(vehicle_number="mh 12-ab 1234"),
        )
        self.assertEqual(response.status_code, 302)
        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.vehicle_number, "MH12AB1234")
        self.assertEqual(vehicle.resident, self.rajesh)

    def test_invalid_plate_is_rejected(self):
        response = self.client.post(
            reverse("admin:vehicles_vehicle_add"),
            self.vehicle_form_data(vehicle_number="ABC123"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid Indian vehicle number")
        self.assertEqual(Vehicle.objects.count(), 0)

    def test_duplicate_plate_typed_differently_is_rejected(self):
        Vehicle.objects.create(resident=self.rajesh, vehicle_number="MH12AB1234")
        response = self.client.post(
            reverse("admin:vehicles_vehicle_add"),
            self.vehicle_form_data(vehicle_number="MH-12-AB-1234"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_plate_search_and_filters(self):
        Vehicle.objects.create(resident=self.rajesh, vehicle_number="MH12AB1234")
        Vehicle.objects.create(
            resident=self.priya,
            vehicle_number="MH14CD5678",
            vehicle_type=Vehicle.VehicleType.TWO_WHEELER,
        )
        list_url = reverse("admin:vehicles_vehicle_changelist")

        # Plate typed with hyphens still finds the stored plate
        response = self.client.get(list_url, {"q": "mh-12-ab"})
        self.assertContains(response, "MH12AB1234")
        self.assertNotContains(response, "MH14CD5678")

        # Filter by vehicle type
        response = self.client.get(list_url, {"vehicle_type__exact": "TWO_WHEELER"})
        self.assertContains(response, "MH14CD5678")
        self.assertNotContains(response, "MH12AB1234")

        # Filter by wing (Vehicle -> Resident -> Flat -> Wing)
        response = self.client.get(list_url, {"resident__flat__wing__id__exact": self.wing_b.pk})
        self.assertContains(response, "MH14CD5678")
        self.assertNotContains(response, "MH12AB1234")

    def test_mark_inactive_action(self):
        vehicle = Vehicle.objects.create(resident=self.rajesh, vehicle_number="MH12AB1234")
        response = self.client.post(
            reverse("admin:vehicles_vehicle_changelist"),
            {"action": "mark_inactive", "_selected_action": [vehicle.pk]},
        )
        self.assertEqual(response.status_code, 302)
        vehicle.refresh_from_db()
        self.assertFalse(vehicle.is_active)

    def test_resident_with_vehicles_cannot_be_deleted(self):
        Vehicle.objects.create(resident=self.rajesh, vehicle_number="MH12AB1234")
        response = self.client.post(
            reverse("admin:residents_resident_changelist"),
            {"action": "delete_selected", "_selected_action": [self.rajesh.pk], "post": "yes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "protected")
        self.assertTrue(Resident.objects.filter(pk=self.rajesh.pk).exists())