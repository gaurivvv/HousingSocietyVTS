from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .testing import TEST_PASSWORD, make_user


class ResidentRedirectAndMyAccountTests(TestCase):
    def setUp(self):
        self.home_url = reverse("dashboard:home")
        self.me_url = reverse("accounts:my_account")

    def test_resident_opening_home_is_sent_to_my_account(self):
        self.client.force_login(make_user("resident", username="resident_asha"))
        response = self.client.get(self.home_url)
        self.assertRedirects(response, self.me_url)

    def test_my_account_page_shows_the_username_and_placeholder(self):
        self.client.force_login(make_user("resident", username="resident_asha"))
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/my_account.html")
        self.assertContains(response, "resident_asha")
        self.assertContains(response, "The resident portal is coming soon.")

    def test_account_with_no_role_is_sent_to_my_account(self):
        self.client.force_login(User.objects.create_user(username="no_role_yet", password=TEST_PASSWORD))
        self.assertRedirects(self.client.get(self.home_url), self.me_url)

    def test_guard_and_society_admin_keep_the_dashboard(self):
        for role in ["guard", "admin"]:
            with self.subTest(role=role):
                self.client.force_login(make_user(role, username=f"home_{role}"))
                response = self.client.get(self.home_url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "dashboard/home.html")
                self.client.logout()

    def test_superuser_keeps_the_dashboard(self):
        self.client.force_login(User.objects.create_superuser(username="owner", password=TEST_PASSWORD))
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/home.html")

    def test_any_logged_in_user_can_open_my_account(self):
        self.client.force_login(make_user("guard", username="guard_ravi"))
        self.assertEqual(self.client.get(self.me_url).status_code, 200)

    def test_my_account_requires_login(self):
        response = self.client.get(self.me_url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.me_url}")

    def test_resident_logging_in_ends_up_on_my_account(self):
        make_user("resident", username="resident_asha")
        response = self.client.post(
            reverse("accounts:login"), {"username": "resident_asha", "password": TEST_PASSWORD}, follow=True
        )
        self.assertRedirects(response, self.me_url)
        self.assertContains(response, "The resident portal is coming soon.")
