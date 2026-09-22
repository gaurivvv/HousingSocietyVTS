from django.test import TestCase
from django.urls import reverse

from tracking.models import VehicleLog

from .testing import make_user

# Every main page of the site; each must require login.
PROTECTED_PAGES = [
    "dashboard:home",
    "residents:resident_list",
    "residents:resident_create",
    "vehicles:vehicle_list",
    "vehicles:vehicle_create",
    "tracking:gate",
    "tracking:history",
    "visitors:visitor_list",
    "visitors:visitor_create",
]


class LoginRequiredTests(TestCase):
    def setUp(self):
        self.login_url = reverse("accounts:login")

    def test_anonymous_visitors_are_sent_to_login_from_every_page(self):
        for name in PROTECTED_PAGES:
            with self.subTest(page=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertRedirects(response, f"{self.login_url}?next={url}")

    def test_anonymous_gate_submission_records_nothing(self):
        response = self.client.post(
            reverse("tracking:gate"),
            {"plate_number": "MH12AB1234", "movement_type": "ENTRY", "category": "UNKNOWN", "remarks": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(self.login_url))
        self.assertEqual(VehicleLog.objects.count(), 0)

    def test_anonymous_visitor_actions_and_detail_pages_redirect_to_login(self):
        for url in [
            reverse("visitors:visitor_detail", args=[99999]),
            reverse("visitors:visitor_check_in", args=[99999]),
        ]:
            with self.subTest(url=url):
                response = self.client.post(url) if "check-in" in url else self.client.get(url)
                # Redirected to login, not a 404: anonymous users cannot probe which records exist
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(self.login_url))

    def test_login_page_stays_public(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    def test_django_admin_uses_its_own_login_page(self):
        response = self.client.get("/admin/")
        self.assertRedirects(response, "/admin/login/?next=/admin/")

    def test_logged_in_user_can_open_pages(self):
        self.client.force_login(make_user("guard"))
        for name in ["dashboard:home", "tracking:gate", "visitors:visitor_list"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_after_login_the_user_returns_to_the_requested_page(self):
        make_user("guard", username="guard_ravi")
        gate_url = reverse("tracking:gate")
        redirect = self.client.get(gate_url)
        self.assertRedirects(redirect, f"{self.login_url}?next={gate_url}")

        response = self.client.post(
            f"{self.login_url}?next={gate_url}",
            {"username": "guard_ravi", "password": "Test-pass-2026!", "next": gate_url},
        )
        self.assertRedirects(response, gate_url)
