"""Tests for the ANPR API endpoint."""

from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.testing import make_user
from tracking.models import VehicleLog


class APIANPRScanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin", username="api_anpr_admin")
        cls.guard = make_user("guard", username="api_anpr_guard")
        cls.resident = make_user("resident", username="api_anpr_res")

    def test_anpr_api_scan_permission_denied_for_resident(self):
        """Residents receive 403 Forbidden when calling the ANPR scan endpoint."""
        self.client.force_login(self.resident)
        url = reverse("api:gate-anpr-scan")
        response = self.client.post(url, {"image": SimpleUploadedFile("car.jpg", b"fakeimg")})
        self.assertEqual(response.status_code, 403)

    def test_anpr_api_scan_missing_image(self):
        """Calling without an image returns 400 Bad Request."""
        self.client.force_login(self.guard)
        url = reverse("api:gate-anpr-scan")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "image_required")

    @patch("api.views.run_anpr")
    def test_anpr_api_scan_success_not_recorded(self, mock_anpr):
        """Successful scan returns candidate detection and does not record a movement."""
        mock_anpr.return_value = {
            "success": True,
            "candidate_plate": "MH12KL4567",
            "raw_text": "MH 12 KL 4567",
            "vehicle_detected": True,
            "vehicle_type": "car",
            "vehicle_confidence": 0.89,
            "plate_detected": True,
            "plate_confidence": 0.92,
            "ocr_confidence": 0.94,
            "format_status": "valid_standard",
            "corrections": [],
            "uncertain": False,
        }

        initial_count = VehicleLog.objects.count()
        self.client.force_login(self.guard)
        url = reverse("api:gate-anpr-scan")
        response = self.client.post(
            url,
            {"image": SimpleUploadedFile("car.jpg", b"imagedata", content_type="image/jpeg")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["candidate_plate"], "MH12KL4567")
        self.assertFalse(data["recorded"])
        self.assertIn("instruction", data)

        # Confirm database state was NOT modified
        self.assertEqual(VehicleLog.objects.count(), initial_count)

    def test_anpr_log_post_still_rejects_source_anpr(self):
        """The existing invariant is preserved: source='anpr' is rejected with 422."""
        self.client.force_login(self.guard)
        url = reverse("api:gate-movement")
        payload = {
            "plate_number": "MH12KL4567",
            "movement_type": "ENTRY",
            "source": "anpr",
        }
        response = self.client.post(url, payload, content_type="application/json")
        self.assertEqual(response.status_code, 422)
