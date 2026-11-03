"""Tests for the Guard ANPR scan view and prefill workflow."""

from io import BytesIO
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.testing import make_user
from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle
from visitors.models import Visitor


class GuardANPRViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.guard = make_user("guard", username="guard_anpr_tester")
        cls.resident_user = make_user("resident", username="res_anpr_tester")

        wing = Wing.objects.create(name="A")
        flat = Flat.objects.create(wing=wing, flat_number="101")
        cls.resident = Resident.objects.create(
            flat=flat,
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        cls.reg_vehicle = Vehicle.objects.create(
            resident=cls.resident,
            vehicle_number="MH12AB1234",
            vehicle_type=Vehicle.VehicleType.FOUR_WHEELER,
        )

        cls.visitor = Visitor.objects.create(
            full_name="Amit Verma",
            phone="9876543211",
            flat=flat,
            resident=cls.resident,
            vehicle_number="MH14CD5678",
            expected_date=timezone.localdate(),
        )

    def test_anpr_scan_permission_required(self):
        """Resident receives 403 Forbidden on the ANPR scan endpoint."""
        self.client.force_login(self.resident_user)
        url = reverse("tracking:anpr_scan")
        response = self.client.post(url, {"image": SimpleUploadedFile("car.jpg", b"fakeimg")})
        self.assertEqual(response.status_code, 403)

    def test_anpr_scan_missing_image(self):
        """Guard receives 400 Bad Request if no image is uploaded."""
        self.client.force_login(self.guard)
        url = reverse("tracking:anpr_scan")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    @patch("tracking.views.run_anpr")
    def test_anpr_scan_registered_vehicle_candidate(self, mock_anpr):
        """Scanning a registered plate returns candidate details and owner match without saving a log."""
        mock_anpr.return_value = {
            "success": True,
            "candidate_plate": "MH12AB1234",
            "raw_text": "MH 12 AB 1234",
            "vehicle_detected": True,
            "vehicle_type": "car",
            "plate_detected": True,
            "plate_confidence": 0.88,
            "ocr_confidence": 0.91,
            "corrections": [],
            "uncertain": False,
        }

        initial_count = VehicleLog.objects.count()
        self.client.force_login(self.guard)
        url = reverse("tracking:anpr_scan")
        response = self.client.post(
            url,
            {"image": SimpleUploadedFile("car.jpg", b"imgcontent", content_type="image/jpeg")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["candidate_plate"], "MH12AB1234")
        self.assertEqual(data["match_type"], "registered")
        self.assertIn("Rajesh Sharma", data["owner_info"])

        # Crucial invariant: ANPR scanning must NOT create a VehicleLog
        self.assertEqual(VehicleLog.objects.count(), initial_count)

    @patch("tracking.views.run_anpr")
    def test_anpr_scan_expected_visitor_candidate(self, mock_anpr):
        """Scanning an expected visitor's plate matches visitor without creating a log."""
        mock_anpr.return_value = {
            "success": True,
            "candidate_plate": "MH14CD5678",
            "raw_text": "MH 14 CD 5678",
            "vehicle_detected": True,
            "vehicle_type": "car",
            "plate_detected": True,
            "plate_confidence": 0.75,
            "ocr_confidence": 0.85,
        }

        self.client.force_login(self.guard)
        url = reverse("tracking:anpr_scan")
        response = self.client.post(
            url,
            {"image": SimpleUploadedFile("car.jpg", b"imgcontent", content_type="image/jpeg")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["match_type"], "visitor")
        self.assertIn("Amit Verma", data["owner_info"])

    @patch("tracking.views.run_anpr")
    def test_anpr_scan_unknown_vehicle_candidate(self, mock_anpr):
        """Scanning an unrecognised plate marks it as unknown match."""
        mock_anpr.return_value = {
            "success": True,
            "candidate_plate": "DL01ZZ9999",
            "vehicle_detected": True,
            "vehicle_type": "car",
            "plate_detected": True,
        }

        self.client.force_login(self.guard)
        url = reverse("tracking:anpr_scan")
        response = self.client.post(
            url,
            {"image": SimpleUploadedFile("car.jpg", b"imgcontent", content_type="image/jpeg")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["match_type"], "unknown")
        self.assertIsNone(data["owner_info"])

    def test_gate_view_prefill_query_param(self):
        """Gate view supports pre-filling the plate from the ANPR workflow."""
        self.client.force_login(self.guard)
        url = reverse("tracking:gate") + "?prefill=MH12AB1234"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="MH12AB1234"')
