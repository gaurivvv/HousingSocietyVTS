from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle

from .models import VehicleLog


class TrackingTestData(TestCase):
    """Shared data: one registered car, owned by Rajesh in A-101."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        cls.car = Vehicle.objects.create(resident=cls.rajesh, vehicle_number="MH12AB1234")


class VehicleLogModelTests(TrackingTestData):
    def test_registered_plate_is_normalized_and_linked(self):
        log = VehicleLog.objects.create(plate_number="mh 12-ab 1234", movement_type="ENTRY")
        self.assertEqual(log.plate_number, "MH12AB1234")
        self.assertEqual(log.vehicle, self.car)
        self.assertEqual(log.category, VehicleLog.Category.REGISTERED)

    def test_unknown_vehicle_is_logged_without_a_vehicle_record(self):
        log = VehicleLog.objects.create(plate_number="KA01XY0001", movement_type="ENTRY")
        self.assertIsNone(log.vehicle)
        self.assertEqual(log.category, VehicleLog.Category.UNKNOWN)

    def test_visitor_category_is_kept_for_unregistered_plate(self):
        log = VehicleLog.objects.create(
            plate_number="GJ05AB1111", movement_type="ENTRY", category="VISITOR"
        )
        self.assertIsNone(log.vehicle)
        self.assertEqual(log.category, VehicleLog.Category.VISITOR)

    def test_registered_cannot_be_claimed_for_unregistered_plate(self):
        log = VehicleLog.objects.create(
            plate_number="DL01AA0001", movement_type="EXIT", category="REGISTERED"
        )
        self.assertIsNone(log.vehicle)
        self.assertEqual(log.category, VehicleLog.Category.UNKNOWN)

    def test_too_short_plate_is_rejected(self):
        log = VehicleLog(plate_number="AB", movement_type="ENTRY")
        with self.assertRaises(ValidationError) as context:
            log.full_clean()
        self.assertIn("plate_number", context.exception.message_dict)

    def test_vehicle_with_gate_history_cannot_be_deleted(self):
        VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="ENTRY")
        with self.assertRaises(ProtectedError):
            self.car.delete()

    def test_logs_are_listed_newest_first(self):
        now = timezone.now()
        older = VehicleLog.objects.create(
            plate_number="MH12AB1234", movement_type="ENTRY", timestamp=now - timedelta(hours=2)
        )
        newer = VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="EXIT", timestamp=now)
        self.assertEqual(list(VehicleLog.objects.all()), [newer, older])
        self.assertEqual(list(self.car.logs.all()), [newer, older])


class VehicleLogAdminTests(TrackingTestData):
    def setUp(self):
        admin_user = get_user_model().objects.create_superuser(
            username="testadmin", password="Test-admin-pass-2026"
        )
        self.client.force_login(admin_user)

    def test_add_log_in_admin_normalizes_and_classifies(self):
        response = self.client.post(
            reverse("admin:tracking_vehiclelog_add"),
            {
                "plate_number": "mh 12-ab 1234",
                "movement_type": "ENTRY",
                "category": "UNKNOWN",
                "timestamp_0": "2026-09-21",
                "timestamp_1": "10:30:00",
                "remarks": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        log = VehicleLog.objects.get()
        self.assertEqual(log.plate_number, "MH12AB1234")
        self.assertEqual(log.vehicle, self.car)
        self.assertEqual(log.category, VehicleLog.Category.REGISTERED)

    def test_add_unknown_log_in_admin(self):
        response = self.client.post(
            reverse("admin:tracking_vehiclelog_add"),
            {
                "plate_number": "KA01XY0001",
                "movement_type": "ENTRY",
                "category": "UNKNOWN",
                "timestamp_0": "2026-09-21",
                "timestamp_1": "10:35:00",
                "remarks": "Delivery van",
            },
        )
        self.assertEqual(response.status_code, 302)
        log = VehicleLog.objects.get()
        self.assertIsNone(log.vehicle)
        self.assertEqual(log.remarks, "Delivery van")

    def test_plate_search_and_category_filter(self):
        VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="ENTRY")
        VehicleLog.objects.create(plate_number="KA01XY0001", movement_type="ENTRY")
        list_url = reverse("admin:tracking_vehiclelog_changelist")

        response = self.client.get(list_url, {"q": "ka-01-xy"})
        self.assertContains(response, "KA01XY0001")
        self.assertNotContains(response, "MH12AB1234")

        response = self.client.get(list_url, {"category__exact": "REGISTERED"})
        self.assertContains(response, "MH12AB1234")
        self.assertNotContains(response, "KA01XY0001")

    def test_list_shows_owner_for_registered_vehicles(self):
        VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="ENTRY")
        response = self.client.get(reverse("admin:tracking_vehiclelog_changelist"))
        self.assertContains(response, "Rajesh Sharma")

    def test_gate_logs_cannot_be_deleted_in_admin(self):
        log = VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="ENTRY")
        response = self.client.get(reverse("admin:tracking_vehiclelog_delete", args=[log.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(VehicleLog.objects.filter(pk=log.pk).exists())
