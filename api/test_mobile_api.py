"""Unit tests for the mobile app endpoints in the REST API."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.testing import TEST_PASSWORD, make_user
from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle
from visitors.models import Visitor


class MobileAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin", username="mobile_admin")
        cls.guard = make_user("guard", username="mobile_guard")
        cls.resident_user = make_user("resident", username="mobile_resident")

        cls.wing = Wing.objects.create(name="M")
        cls.flat = Flat.objects.create(wing=cls.wing, flat_number="202")
        cls.resident = Resident.objects.create(
            flat=cls.flat,
            user=cls.resident_user,
            full_name="Pooja Kulkarni",
            phone="9876543220",
        )
        cls.vehicle = Vehicle.objects.create(
            resident=cls.resident,
            vehicle_number="MH12PQ9999",
            vehicle_type=Vehicle.VehicleType.FOUR_WHEELER,
        )

    def test_mobile_login_success_resident(self):
        """Resident can log in and receive token, role, and resident context."""
        url = reverse("api:auth-login")
        payload = {"username": "mobile_resident", "password": TEST_PASSWORD}
        response = self.client.post(url, payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("token", data)
        self.assertEqual(data["username"], "mobile_resident")
        self.assertEqual(data["role"], "Resident")
        self.assertIsNotNone(data["resident"])
        self.assertEqual(data["resident"]["full_name"], "Pooja Kulkarni")

    def test_mobile_login_success_guard(self):
        """Guard can log in and receive role Guard without resident profile."""
        url = reverse("api:auth-login")
        payload = {"username": "mobile_guard", "password": TEST_PASSWORD}
        response = self.client.post(url, payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["role"], "Guard")
        self.assertIsNone(data["resident"])

    def test_mobile_login_invalid_password(self):
        """Invalid credentials return 401 Unauthorized."""
        url = reverse("api:auth-login")
        payload = {"username": "mobile_resident", "password": "WrongPassword123"}
        response = self.client.post(url, payload, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_resident_me_endpoint(self):
        """Resident can fetch their own vehicles and visitors."""
        self.client.force_login(self.resident_user)
        url = reverse("api:resident-me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["full_name"], "Pooja Kulkarni")
        self.assertEqual(data["flat_name"], "M-202")
        self.assertEqual(len(data["vehicles"]), 1)
        self.assertEqual(data["vehicles"][0]["vehicle_number"], "MH12PQ9999")

    def test_resident_pre_register_visitor(self):
        """Resident can pre-register a visitor from their phone."""
        self.client.force_login(self.resident_user)
        url = reverse("api:resident-create-visitor")
        payload = {
            "full_name": "Rohan Deshmukh",
            "phone": "9876543221",
            "vehicle_number": "MH12XY1234",
            "expected_date": str(timezone.localdate()),
        }
        response = self.client.post(url, payload, content_type="application/json")

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["full_name"], "Rohan Deshmukh")
        self.assertTrue(data["pass_code"].startswith("VP-"))
        self.assertEqual(data["status"], "EXPECTED")

    def test_guard_visitor_list_and_check_in_out(self):
        """Guard can fetch today's visitors and trigger check-in and check-out."""
        visitor = Visitor.objects.create(
            full_name="Karan Malhotra",
            phone="9876543222",
            flat=self.flat,
            resident=self.resident,
            expected_date=timezone.localdate(),
        )

        self.client.force_login(self.guard)
        # 1. Guard views visitors
        list_url = reverse("api:guard-visitor-list")
        res = self.client.get(list_url)
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.json()["count"], 1)

        # 2. Guard checks in visitor
        checkin_url = reverse("api:visitor-check-in", kwargs={"pk": visitor.pk})
        res_in = self.client.post(checkin_url)
        self.assertEqual(res_in.status_code, 200)
        self.assertEqual(res_in.json()["status"], "CHECKED_IN")

        # 3. Guard checks out visitor
        checkout_url = reverse("api:visitor-check-out", kwargs={"pk": visitor.pk})
        res_out = self.client.post(checkout_url)
        self.assertEqual(res_out.status_code, 200)
        self.assertEqual(res_out.json()["status"], "CHECKED_OUT")

    def test_dashboard_stats_permission(self):
        """Guards and admins can view society stats; residents are denied with 403."""
        url = reverse("api:dashboard-stats")

        # Resident denied
        self.client.force_login(self.resident_user)
        res_res = self.client.get(url)
        self.assertEqual(res_res.status_code, 403)

        # Guard allowed
        self.client.force_login(self.guard)
        res_guard = self.client.get(url)
        self.assertEqual(res_guard.status_code, 200)
        data = res_guard.json()
        self.assertIn("inside_count", data)
        self.assertIn("active_resident_count", data)
