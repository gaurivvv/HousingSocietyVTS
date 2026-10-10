"""Tests for the gate log audit field.

recorded_by answers one question: who recorded this movement? It is set from
the authenticated session and never from client-supplied data, so a caller
cannot attribute a movement to someone else.

NULL is a legitimate value. Records created before the field existed, and
records created by a management command or a script, have no signed-in user.
NULL says that honestly rather than naming someone who did not record them.
"""

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from accounts.testing import make_user
from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle


class AuditTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin", username="audit_admin")
        cls.guard = make_user("guard", username="audit_guard")
        cls.resident_user = make_user("resident", username="audit_resident")

        wing = Wing.objects.create(name="Z")
        flat = Flat.objects.create(wing=wing, flat_number="501")
        cls.resident = Resident.objects.create(
            flat=flat, full_name="Audit Testperson", resident_type="OWNER",
            phone="9000000009",
        )
        cls.vehicle = Vehicle.objects.create(
            resident=cls.resident, vehicle_number="MH88AU1234",
            vehicle_type="FOUR_WHEELER",
        )


class GateFormAuditTests(AuditTestBase):
    """The gate page records the signed-in user."""

    def setUp(self):
        self.url = reverse("tracking:gate")

    def test_guard_submission_records_the_guard(self):
        self.client.force_login(self.guard)
        self.client.post(self.url, {
            "plate_number": "MH88AU1234", "movement_type": "ENTRY",
            "category": "UNKNOWN", "remarks": "",
        })
        log = VehicleLog.objects.filter(plate_number="MH88AU1234").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.recorded_by, self.guard)

    def test_admin_submission_records_the_admin(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {
            "plate_number": "KA09AU5555", "movement_type": "EXIT",
            "category": "UNKNOWN", "remarks": "",
        })
        log = VehicleLog.objects.filter(plate_number="KA09AU5555").first()
        self.assertEqual(log.recorded_by, self.admin)

    def test_posted_recorded_by_is_ignored(self):
        """A crafted POST cannot attribute the movement to someone else.

        GateEntryForm has no recorded_by field, so the extra value is simply
        not part of the form at all.
        """
        self.client.force_login(self.guard)
        self.client.post(self.url, {
            "plate_number": "KA09AU6666", "movement_type": "ENTRY",
            "category": "UNKNOWN", "remarks": "",
            "recorded_by": self.admin.pk,
            "recorded_by_id": self.admin.pk,
        })
        log = VehicleLog.objects.filter(plate_number="KA09AU6666").first()
        self.assertEqual(log.recorded_by, self.guard)
        self.assertNotEqual(log.recorded_by, self.admin)

    def test_classification_still_works_with_the_audit_field(self):
        """Adding recorded_by must not disturb _apply_rules()."""
        self.client.force_login(self.guard)
        self.client.post(self.url, {
            "plate_number": "mh 88 au 1234", "movement_type": "ENTRY",
            "category": "UNKNOWN", "remarks": "",
        })
        log = VehicleLog.objects.filter(plate_number="MH88AU1234").first()
        self.assertEqual(log.category, "REGISTERED")
        self.assertEqual(log.vehicle, self.vehicle)
        self.assertEqual(log.recorded_by, self.guard)


class ApiAuditTests(AuditTestBase):
    """The API records the authenticated caller, not anything they send."""

    def setUp(self):
        self.url = reverse("api:gate-movement")

    def post(self, payload):
        return self.client.post(self.url, payload, content_type="application/json")

    def test_api_records_the_caller(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "MH88AU1234",
                              "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.status_code, 201)
        log = VehicleLog.objects.get(pk=response.json()["log"]["id"])
        self.assertEqual(log.recorded_by, self.guard)

    def test_supplied_recorded_by_is_ignored(self):
        """A guard cannot make a movement look like the administrator's."""
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "KA09AU7777", "movement_type": "ENTRY",
                              "source": "manual", "recorded_by": self.admin.pk})
        self.assertEqual(response.status_code, 201)
        log = VehicleLog.objects.get(pk=response.json()["log"]["id"])
        self.assertEqual(log.recorded_by, self.guard)
        self.assertIn("recorded_by", response.json()["ignored_fields"])

    def test_supplied_user_field_is_ignored(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "KA09AU8888", "movement_type": "ENTRY",
                              "source": "manual", "user": self.admin.pk,
                              "user_id": self.admin.pk})
        self.assertEqual(response.status_code, 201)
        log = VehicleLog.objects.get(pk=response.json()["log"]["id"])
        self.assertEqual(log.recorded_by, self.guard)
        self.assertIn("user", response.json()["ignored_fields"])

    def test_response_shows_the_username_only(self):
        self.client.force_login(self.guard)
        response = self.post({"plate_number": "KA09AU9999",
                              "movement_type": "ENTRY", "source": "manual"})
        self.assertEqual(response.json()["log"]["recorded_by"], "audit_guard")

    def test_response_exposes_no_other_user_details(self):
        """Only the username. No id, no email, no staff flags."""
        self.client.force_login(self.admin)
        response = self.post({"plate_number": "KA09AU1010",
                              "movement_type": "ENTRY", "source": "manual"})
        body = response.content.decode()
        self.assertNotIn("is_staff", body)
        self.assertNotIn("is_superuser", body)
        self.assertNotIn("password", body)
        self.assertNotIn("recorded_by_id", body)

    def test_gate_log_list_shows_recorded_by(self):
        self.client.force_login(self.guard)
        self.post({"plate_number": "KA09AU1111",
                   "movement_type": "ENTRY", "source": "manual"})
        rows = self.client.get(reverse("api:gate-log-list"),
                               {"plate": "KA09AU1111"}).json()["results"]
        self.assertTrue(rows)
        self.assertEqual(rows[0]["recorded_by"], "audit_guard")


class SystemCreatedLogTests(AuditTestBase):
    """Logs created without a request remain valid, with recorded_by NULL."""

    def test_log_created_without_a_user_is_allowed(self):
        """The seed command and scripts create logs with no signed-in user."""
        log = VehicleLog.objects.create(plate_number="KA09AU2222",
                                        movement_type="ENTRY")
        self.assertIsNone(log.recorded_by)

    def test_such_a_log_is_still_classified(self):
        log = VehicleLog.objects.create(plate_number="MH88AU1234",
                                        movement_type="ENTRY")
        self.assertEqual(log.category, "REGISTERED")
        self.assertIsNone(log.recorded_by)

    def test_api_reports_null_for_an_unattributed_log(self):
        VehicleLog.objects.create(plate_number="KA09AU3333", movement_type="ENTRY")
        self.client.force_login(self.guard)
        rows = self.client.get(reverse("api:gate-log-list"),
                               {"plate": "KA09AU3333"}).json()["results"]
        self.assertTrue(rows)
        self.assertIsNone(rows[0]["recorded_by"])


class AuditTrailProtectionTests(AuditTestBase):
    """PROTECT keeps the audit trail intact when a user is removed."""

    def test_deleting_a_user_who_recorded_a_log_is_refused(self):
        """Deleting the user would erase who recorded the movement."""
        VehicleLog.objects.create(plate_number="KA09AU4444",
                                  movement_type="ENTRY", recorded_by=self.guard)
        with self.assertRaises(ProtectedError):
            self.guard.delete()
        self.assertTrue(User.objects.filter(pk=self.guard.pk).exists())

    def test_a_user_with_no_logs_can_still_be_deleted(self):
        spare = make_user("guard", username="audit_spare")
        spare.delete()
        self.assertFalse(User.objects.filter(username="audit_spare").exists())

    def test_deactivating_instead_of_deleting_works(self):
        """The supported way to retire an account without losing history."""
        VehicleLog.objects.create(plate_number="KA09AU5050",
                                  movement_type="ENTRY", recorded_by=self.guard)
        self.guard.is_active = False
        self.guard.save()
        log = VehicleLog.objects.get(plate_number="KA09AU5050")
        self.assertEqual(log.recorded_by, self.guard)


class ExistingRecordCompatibilityTests(AuditTestBase):
    """Records that predate the field keep working everywhere."""

    def test_unattributed_log_appears_in_gate_history(self):
        VehicleLog.objects.create(plate_number="KA09AU6060", movement_type="ENTRY")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("tracking:history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KA09AU6060")

    def test_unattributed_log_appears_on_the_gate_page(self):
        VehicleLog.objects.create(plate_number="KA09AU7070", movement_type="ENTRY")
        self.client.force_login(self.guard)
        response = self.client.get(reverse("tracking:gate"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KA09AU7070")
