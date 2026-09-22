from django.test import TestCase
from django.urls import reverse

from .testing import TEST_PASSWORD, make_user


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.guard = make_user("guard", username="guard_ravi")
        self.login_url = reverse("accounts:login")

    def log_in(self, password=TEST_PASSWORD, next_url=None, username="guard_ravi"):
        data = {"username": username, "password": password}
        if next_url is not None:
            data["next"] = next_url
        return self.client.post(self.login_url, data)

    def test_login_page_loads(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertContains(response, 'name="password"')

    def test_valid_login_goes_home_and_shows_the_username(self):
        response = self.log_in()
        self.assertRedirects(response, reverse("dashboard:home"))
        home = self.client.get(reverse("dashboard:home"))
        self.assertContains(home, "Signed in as")
        self.assertContains(home, "guard_ravi")
        self.assertContains(home, "Log out")

    def test_wrong_password_is_rejected_without_saying_which_field(self):
        response = self.log_in(password="wrong-password")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_username_gets_the_same_message(self):
        response = self.log_in(username="nobody")
        self.assertContains(response, "Please enter a correct username and password")

    def test_inactive_user_cannot_log_in(self):
        self.guard.is_active = False
        self.guard.save()
        self.log_in()
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_returns_to_the_requested_page(self):
        response = self.log_in(next_url=reverse("tracking:gate"))
        self.assertRedirects(response, reverse("tracking:gate"))

    def test_login_ignores_a_next_address_on_another_website(self):
        response = self.log_in(next_url="https://evil.example.com/")
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_logged_in_user_visiting_login_page_goes_home(self):
        self.client.force_login(self.guard)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_logout_requires_post_and_returns_to_login(self):
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, self.login_url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_navbar_shows_log_in_link_when_logged_out(self):
        response = self.client.get(self.login_url)
        self.assertContains(response, "Log in")
        self.assertNotContains(response, "Signed in as")
