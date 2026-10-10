"""Tests for the API layer.

Checkpoint 1: DRF wiring and authentication.
Checkpoint 2: vehicle list and lookup, including the privacy guarantee that
owner contact details never appear in an API response.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.roles import GUARD, RESIDENT
from accounts.testing import make_user
from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle


class ApiTestBase(TestCase):
    """Shared users and data for the API tests."""

    @classmethod
    def setUpTestData(cls):
        # make_user() runs setup_roles first, so the groups carry their real
        # permissions. Creating a Group directly would give an empty group and
        # every permission check would fail for reasons unrelated to the API.
        cls.admin = make_user("admin", username="api_admin")
        cls.guard = make_user("guard", username="api_guard")
        cls.resident_user = make_user("resident", username="api_resident")

        wing = Wing.objects.create(name="T")
        flat = Flat.objects.create(wing=wing, flat_number="901")
        cls.resident = Resident.objects.create(
            flat=flat,
            full_name="Api Testperson",
            resident_type="OWNER",
            phone="9000000001",
            email="api.testperson@example.com",
        )
        cls.vehicle = Vehicle.objects.create(
            resident=cls.resident,
            vehicle_number="MH99XY1111",
            vehicle_type="FOUR_WHEELER",
            model_name="Test Model",
            colour="Grey",
        )


class PingEndpointTests(ApiTestBase):
    """The ping endpoint confirms DRF is wired up and authentication applies."""

    def setUp(self):
        self.url = reverse("api:ping")

    def test_anonymous_request_is_refused(self):
        """Anonymous API requests get 403, not a redirect to the login page.

        LoginRequiredMiddleware defers to the view, and DRF's IsAuthenticated
        permission then refuses the request. Because SessionAuthentication has
        no authenticate_header, DRF returns 403 rather than 401. This is the
        right behaviour for an API: a machine-readable refusal rather than an
        HTML login page.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_reach_the_endpoint(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["user"], "api_admin")
        self.assertEqual(response.json()["api_version"], "v1")

    def test_guard_can_reach_the_endpoint(self):
        self.client.force_login(self.guard)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["groups"], [GUARD])

    def test_resident_can_reach_the_endpoint(self):
        """Ping requires only a login; other endpoints add permission checks."""
        self.client.force_login(self.resident_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["groups"], [RESIDENT])

    def test_response_is_json(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response["Content-Type"], "application/json")


class VehicleListTests(ApiTestBase):
    """GET /api/v1/vehicles/ requires vehicles.view_vehicle."""

    def setUp(self):
        self.url = reverse("api:vehicle-list")

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_admin_can_list(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 1)

    def test_guard_can_list(self):
        """Guards can view vehicles in the browser, so they can here too."""
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_resident_is_forbidden(self):
        """Residents hold no permissions and must be refused."""
        self.client.force_login(self.resident_user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_owner_contact_details_are_never_exposed(self):
        """The key privacy guarantee: no phone or email in any response."""
        self.client.force_login(self.guard)
        body = self.client.get(self.url).content.decode()
        self.assertNotIn(self.resident.phone, body)
        self.assertNotIn(self.resident.email, body)
        self.assertNotIn("phone", body)
        self.assertNotIn("email", body)

    def test_owner_name_and_flat_are_present(self):
        """Guards need to know whose vehicle it is, without contact details."""
        self.client.force_login(self.guard)
        body = self.client.get(self.url).content.decode()
        self.assertIn("Api Testperson", body)
        self.assertIn("T-901", body)

    def test_active_filter(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"active": "true"})
        self.assertEqual(response.status_code, 200)
        for row in response.json()["results"]:
            self.assertTrue(row["is_active"])


class VehicleLookupTests(ApiTestBase):
    """GET /api/v1/vehicles/lookup/?plate=... normalizes before matching."""

    def setUp(self):
        self.url = reverse("api:vehicle-lookup")

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get(self.url, {"plate": "MH99XY1111"}).status_code, 403)

    def test_resident_is_forbidden(self):
        self.client.force_login(self.resident_user)
        self.assertEqual(self.client.get(self.url, {"plate": "MH99XY1111"}).status_code, 403)

    def test_exact_plate_is_found(self):
        self.client.force_login(self.guard)
        response = self.client.get(self.url, {"plate": "MH99XY1111"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["registered"])
        self.assertEqual(response.json()["vehicle"]["vehicle_number"], "MH99XY1111")

    def test_plate_with_spaces_is_normalized(self):
        """The existing normalize_plate() handles spacing and case."""
        self.client.force_login(self.guard)
        response = self.client.get(self.url, {"plate": "mh 99 xy 1111"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["normalized"], "MH99XY1111")
        self.assertTrue(response.json()["registered"])

    def test_unknown_plate_returns_404_not_an_accusation(self):
        """Not registered is not the same as unauthorized."""
        self.client.force_login(self.guard)
        response = self.client.get(self.url, {"plate": "KA05ZZ0000"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["registered"])

    def test_missing_plate_parameter_is_rejected(self):
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(self.url).status_code, 400)

    def test_blank_plate_is_rejected(self):
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(self.url, {"plate": "   "}).status_code, 400)

    def test_lookup_does_not_expose_contact_details(self):
        self.client.force_login(self.guard)
        body = self.client.get(self.url, {"plate": "MH99XY1111"}).content.decode()
        self.assertNotIn(self.resident.phone, body)
        self.assertNotIn(self.resident.email, body)

class GateLogListTests(ApiTestBase):
    """GET /api/v1/gate/logs/ requires tracking.view_vehiclelog."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # The model classifies these itself; we only supply plate and direction.
        VehicleLog.objects.create(plate_number="MH99XY1111", movement_type="ENTRY")
        VehicleLog.objects.create(plate_number="KA05ZZ0000", movement_type="ENTRY",
                                  remarks="Courier van")

    def setUp(self):
        self.url = reverse("api:gate-log-list")

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_resident_is_forbidden(self):
        self.client.force_login(self.resident_user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_guard_can_list(self):
        self.client.force_login(self.guard)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 2)

    def test_admin_can_list(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_registered_plate_is_classified_by_the_model(self):
        """The API does not classify; VehicleLog._apply_rules() does."""
        self.client.force_login(self.guard)
        rows = self.client.get(self.url, {"plate": "MH99XY1111"}).json()["results"]
        self.assertTrue(rows)
        self.assertEqual(rows[0]["category"], "REGISTERED")
        self.assertEqual(rows[0]["owner_name"], "Api Testperson")

    def test_unregistered_plate_is_unknown_not_unauthorized(self):
        """UNKNOWN is a classification, not a verdict about the vehicle."""
        self.client.force_login(self.guard)
        rows = self.client.get(self.url, {"plate": "KA05ZZ0000"}).json()["results"]
        self.assertTrue(rows)
        self.assertEqual(rows[0]["category"], "UNKNOWN")
        self.assertIsNone(rows[0]["owner_name"])

    def test_movement_filter(self):
        self.client.force_login(self.guard)
        rows = self.client.get(self.url, {"movement": "ENTRY"}).json()["results"]
        for row in rows:
            self.assertEqual(row["movement_type"], "ENTRY")

    def test_limit_is_capped(self):
        self.client.force_login(self.guard)
        response = self.client.get(self.url, {"limit": "9999"})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(response.json()["returned"], 200)

    def test_no_contact_details_in_gate_logs(self):
        self.client.force_login(self.guard)
        body = self.client.get(self.url).content.decode()
        self.assertNotIn(self.resident.phone, body)
        self.assertNotIn(self.resident.email, body)

class GateMovementTests(ApiTestBase):
    """POST /api/v1/gate/anpr-log/ requires tracking.add_vehiclelog."""

    def setUp(self):
        self.url = reverse("api:gate-movement")

    def post(self, payload):
        return self.client.post(self.url, payload, content_type="application/json")

    def test_anonymous_is_refused(self):
        response = self.post({"plate_number": "MH99XY1111",
                              "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.status_code, 403)

    def test_resident_is_forbidden(self):
        self.client.force_login(self.resident_user)
        response = self.post({"plate_number": "MH99XY1111",
                              "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.status_code, 403)

    def test_guard_can_record_a_confirmed_movement(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "MH99XY1111",
                              "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["created"])
        self.assertEqual(response.json()["log"]["category"], "REGISTERED")

    def test_admin_can_record_a_confirmed_movement(self):
        self.client.force_login(self.admin)
        response = self.post({"plate_number": "KA05ZZ7777",
                              "movement_type": "EXIT", "source": "manual"})
        self.assertEqual(response.status_code, 201)

    def test_anpr_source_is_rejected_with_422(self):
        """The schema cannot store an unverified observation honestly."""
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "MH99XY1111",
                              "movement_type": "ENTRY", "source": "anpr",
                              "ocr_confidence": 0.95})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "unverified_observation_not_storable")
        self.assertEqual(VehicleLog.objects.filter(plate_number="MH99XY1111").count(), 0)

    def test_high_confidence_does_not_unlock_anpr(self):
        """A client-supplied confidence score proves nothing."""
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "MH99XY1111", "movement_type": "ENTRY",
                              "source": "anpr", "ocr_confidence": 1.0,
                              "confirmed_by_guard": True})
        self.assertEqual(response.status_code, 422)

    def test_missing_source_is_rejected(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "MH99XY1111", "movement_type": "ENTRY"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_source")

    def test_missing_plate_is_rejected(self):
        self.client.force_login(self.guard)
        response = self.post({"movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "plate_required")

    def test_blank_plate_is_rejected(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "   ", "movement_type": "ENTRY",
                              "source": "manual"})
        self.assertEqual(response.status_code, 400)

    def test_invalid_movement_type_is_rejected(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "MH99XY1111",
                              "movement_type": "SIDEWAYS", "source": "manual"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_movement_type")

    def test_plate_is_normalized_before_saving(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "mh 99 xy 1111",
                              "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["log"]["plate_number"], "MH99XY1111")

    def test_unknown_plate_is_recorded_as_unknown_not_refused(self):
        """An unrecognised plate is still a real movement worth logging."""
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "KA05ZZ8888",
                              "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["log"]["category"], "UNKNOWN")

    def test_client_cannot_set_the_category(self):
        """Classification belongs to the model, not the caller."""
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "KA05ZZ9999", "movement_type": "ENTRY",
                              "source": "manual", "category": "REGISTERED"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["log"]["category"], "UNKNOWN")
        self.assertIn("category", response.json()["ignored_fields"])

    def test_client_cannot_claim_an_owner(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "KA05ZZ6666", "movement_type": "ENTRY",
                              "source": "manual", "resident_id": self.resident.pk})
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["log"]["owner_name"])
        self.assertIn("resident_id", response.json()["ignored_fields"])

    def test_duplicate_within_the_window_creates_nothing(self):
        self.client.force_login(self.guard)
        first = self.post({"plate_number": "MH99XY1111",
                           "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(first.status_code, 201)

        second = self.post({"plate_number": "MH99XY1111",
                            "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertTrue(second.json()["duplicate_of_recent_movement"])
        self.assertEqual(VehicleLog.objects.filter(plate_number="MH99XY1111").count(), 1)

    def test_opposite_direction_is_not_a_duplicate(self):
        self.client.force_login(self.guard)
        self.post({"plate_number": "MH99XY1111", "movement_type": "ENTRY", "source": "manual"})
        exit_response = self.post({"plate_number": "MH99XY1111",
                                   "movement_type": "EXIT", "source": "manual"})
        self.assertEqual(exit_response.status_code, 201)
        self.assertEqual(VehicleLog.objects.filter(plate_number="MH99XY1111").count(), 2)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_response_contains_no_contact_details(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "MH99XY1111",
                              "movement_type": "ENTRY", "source": "manual"})
        body = response.content.decode()
        self.assertNotIn(self.resident.phone, body)
        self.assertNotIn(self.resident.email, body)
