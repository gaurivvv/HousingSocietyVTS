from django.test import TestCase
from django.urls import reverse

from .testing import make_user

FRIENDLY_MESSAGE = "You don't have permission to open this page."


class FriendlyForbiddenPageTests(TestCase):
    def get_as(self, role, url, method="get"):
        self.client.force_login(make_user(role, username=f"forbidden_{role}"))
        return getattr(self.client, method)(url)

    def assert_friendly_403(self, response):
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, FRIENDLY_MESSAGE, status_code=403)
        self.assertContains(response, f'href="{reverse("dashboard:home")}" class="btn btn-primary">Go to Home</a>', status_code=403)
        self.assertContains(response, "Signed in as", status_code=403)

    def test_guard_opening_residents_gets_the_friendly_page(self):
        self.assert_friendly_403(self.get_as("guard", reverse("residents:resident_list")))

    def test_resident_opening_the_gate_gets_the_friendly_page(self):
        self.assert_friendly_403(self.get_as("resident", reverse("tracking:gate")))

    def test_resident_posting_a_visitor_action_gets_the_friendly_page(self):
        self.assert_friendly_403(
            self.get_as("resident", reverse("visitors:visitor_check_in", args=[99999]), method="post")
        )
