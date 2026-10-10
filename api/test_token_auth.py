"""Tests for API token authentication.

A token identifies a user. It does not grant permissions: the user's group
membership still decides what each endpoint allows. A token belonging to a
user without permission is refused exactly as a session login would be.

Every token here is created inside the test database and destroyed with it.
No real token or password appears in this file.
"""

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from io import StringIO

from rest_framework.authtoken.models import Token

from accounts.roles import RESIDENT
from accounts.testing import make_user
from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle


class TokenTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin", username="tok_admin")
        cls.guard = make_user("guard", username="tok_guard")
        cls.resident_user = make_user("resident", username="tok_resident")

        # Tokens exist only in the test database.
        cls.guard_token = Token.objects.create(user=cls.guard)
        cls.resident_token = Token.objects.create(user=cls.resident_user)
        cls.admin_token = Token.objects.create(user=cls.admin)

        wing = Wing.objects.create(name="T")
        flat = Flat.objects.create(wing=wing, flat_number="701")
        cls.resident = Resident.objects.create(
            flat=flat, full_name="Token Testperson",
            resident_type="OWNER", phone="9000000007",
        )
        cls.vehicle = Vehicle.objects.create(
            resident=cls.resident, vehicle_number="MH77TK1234",
            vehicle_type="FOUR_WHEELER",
        )

    def with_token(self, token, url, params=None):
        return self.client.get(url, params or {},
                               HTTP_AUTHORIZATION=f"Token {token.key}")


class TokenAuthenticationTests(TokenTestBase):
    """A valid token authenticates; a bad one does not."""

    def setUp(self):
        self.url = reverse("api:vehicle-list")

    def test_no_credentials_is_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_valid_guard_token_is_accepted(self):
        response = self.with_token(self.guard_token, self.url)
        self.assertEqual(response.status_code, 200)

    def test_invalid_token_is_401(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION="Token not-a-real-key")
        self.assertEqual(response.status_code, 401)

    def test_malformed_header_is_401(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION="Token")
        self.assertEqual(response.status_code, 401)

    def test_wrong_scheme_is_401(self):
        """Bearer is not the scheme DRF's TokenAuthentication expects."""
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.guard_token.key}")
        self.assertEqual(response.status_code, 401)

    def test_revoked_token_stops_working(self):
        self.assertEqual(self.with_token(self.guard_token, self.url).status_code, 200)
        Token.objects.filter(user=self.guard).delete()
        self.assertEqual(self.with_token(self.guard_token, self.url).status_code, 401)

    def test_token_identifies_the_right_user(self):
        response = self.with_token(self.guard_token, reverse("api:ping"))
        self.assertEqual(response.json()["user"], "tok_guard")


class TokenDoesNotGrantPermissionTests(TokenTestBase):
    """The central safety property: a token authenticates, it does not authorize."""

    def test_resident_token_is_forbidden_on_vehicles(self):
        response = self.with_token(self.resident_token, reverse("api:vehicle-list"))
        self.assertEqual(response.status_code, 403)

    def test_resident_token_is_forbidden_on_lookup(self):
        response = self.with_token(self.resident_token,
                                   reverse("api:vehicle-lookup"),
                                   {"plate": "MH77TK1234"})
        self.assertEqual(response.status_code, 403)

    def test_resident_token_is_forbidden_on_gate_logs(self):
        response = self.with_token(self.resident_token, reverse("api:gate-log-list"))
        self.assertEqual(response.status_code, 403)

    def test_resident_token_cannot_record_a_movement(self):
        response = self.client.post(
            reverse("api:gate-movement"),
            {"plate_number": "MH77TK1234", "movement_type": "ENTRY", "source": "manual"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.resident_token.key}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(VehicleLog.objects.filter(plate_number="MH77TK1234").count(), 0)

    def test_resident_token_still_reaches_ping(self):
        """Ping needs only authentication, so a resident token works there."""
        response = self.with_token(self.resident_token, reverse("api:ping"))
        self.assertEqual(response.status_code, 200)


class TokenAndSessionCoexistTests(TokenTestBase):
    """Adding tokens must not disturb the browser session path."""

    def test_session_login_still_works(self):
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(reverse("api:vehicle-list")).status_code, 200)

    def test_token_and_session_give_the_same_data(self):
        token_body = self.with_token(self.guard_token,
                                     reverse("api:vehicle-list")).json()
        self.client.force_login(self.guard)
        session_body = self.client.get(reverse("api:vehicle-list")).json()
        self.assertEqual(token_body["count"], session_body["count"])

    def test_browser_pages_are_unaffected(self):
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(reverse("tracking:gate")).status_code, 200)


class TokenRecordsTheRightUserTests(TokenTestBase):
    """A movement submitted with a token is attributed to that token's owner."""

    def test_gate_movement_records_the_token_owner(self):
        response = self.client.post(
            reverse("api:gate-movement"),
            {"plate_number": "MH77TK1234", "movement_type": "ENTRY", "source": "manual"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.guard_token.key}",
        )
        self.assertEqual(response.status_code, 201)
        log = VehicleLog.objects.get(pk=response.json()["log"]["id"])
        self.assertEqual(log.recorded_by, self.guard)

    def test_a_token_cannot_attribute_to_someone_else(self):
        response = self.client.post(
            reverse("api:gate-movement"),
            {"plate_number": "KA09TK5555", "movement_type": "ENTRY",
             "source": "manual", "recorded_by": self.admin.pk},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.guard_token.key}",
        )
        self.assertEqual(response.status_code, 201)
        log = VehicleLog.objects.get(pk=response.json()["log"]["id"])
        self.assertEqual(log.recorded_by, self.guard)


class TokenNeverLeaksTests(TokenTestBase):
    """No endpoint returns a token value."""

    def test_token_value_absent_from_api_responses(self):
        for url in [reverse("api:ping"), reverse("api:vehicle-list"),
                    reverse("api:gate-log-list")]:
            body = self.with_token(self.guard_token, url).content.decode()
            self.assertNotIn(self.guard_token.key, body)
            self.assertNotIn(self.admin_token.key, body)


class ApiTokenCommandTests(TestCase):
    """The provisioning command refuses unsuitable accounts."""

    @classmethod
    def setUpTestData(cls):
        cls.guard = make_user("guard", username="cmd_guard")
        cls.resident_user = make_user("resident", username="cmd_resident")

    def run_command(self, *args):
        out = StringIO()
        call_command("api_token", *args, stdout=out)
        return out.getvalue()

    def test_issue_creates_a_token(self):
        output = self.run_command("issue", "cmd_guard")
        self.assertTrue(Token.objects.filter(user=self.guard).exists())
        self.assertIn("Token issued", output)

    def test_issue_refuses_a_resident(self):
        with self.assertRaises(CommandError):
            self.run_command("issue", "cmd_resident")
        self.assertFalse(Token.objects.filter(user=self.resident_user).exists())

    def test_issue_refuses_an_inactive_user(self):
        self.guard.is_active = False
        self.guard.save()
        with self.assertRaises(CommandError):
            self.run_command("issue", "cmd_guard")

    def test_issue_refuses_to_overwrite_without_rotate(self):
        self.run_command("issue", "cmd_guard")
        with self.assertRaises(CommandError):
            self.run_command("issue", "cmd_guard")

    def test_rotate_replaces_the_token(self):
        self.run_command("issue", "cmd_guard")
        first = Token.objects.get(user=self.guard).key
        self.run_command("issue", "cmd_guard", "--rotate")
        second = Token.objects.get(user=self.guard).key
        self.assertNotEqual(first, second)

    def test_show_does_not_print_the_whole_key(self):
        self.run_command("issue", "cmd_guard")
        key = Token.objects.get(user=self.guard).key
        output = self.run_command("show", "cmd_guard")
        self.assertNotIn(key, output)
        self.assertIn(key[:8], output)

    def test_revoke_removes_the_token(self):
        self.run_command("issue", "cmd_guard")
        self.run_command("revoke", "cmd_guard")
        self.assertFalse(Token.objects.filter(user=self.guard).exists())

    def test_unknown_user_is_an_error(self):
        with self.assertRaises(CommandError):
            self.run_command("issue", "nobody_here")
