"""Tests for the Recorded By column on the Gate History page.

The column reads the recorded_by audit field. It never accepts a username or
user id from the browser: the value is set server-side when the movement is
recorded, and this page only displays it.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.testing import make_user
from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle


class RecordedByColumnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin", username="hist_admin")
        cls.guard = make_user("guard", username="hist_guard")
        cls.resident_user = make_user("resident", username="hist_resident")

        wing = Wing.objects.create(name="R")
        flat = Flat.objects.create(wing=wing, flat_number="301")
        cls.resident = Resident.objects.create(
            flat=flat, full_name="History Testperson",
            resident_type="OWNER", phone="9000000003",
        )
        cls.vehicle = Vehicle.objects.create(
            resident=cls.resident, vehicle_number="MH66HS1234",
            vehicle_type="FOUR_WHEELER",
        )

        # Attributed: recorded by the guard.
        cls.attributed = VehicleLog.objects.create(
            plate_number="MH66HS1234", movement_type="ENTRY",
            recorded_by=cls.guard,
        )
        # Legacy: no user, as every record created before the audit field.
        cls.legacy = VehicleLog.objects.create(
            plate_number="KA07HS5555", movement_type="ENTRY",
        )

    def setUp(self):
        self.url = reverse("tracking:history")

    def test_column_header_is_present(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url), "Recorded by")

    def test_attributed_log_shows_the_username(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url), "hist_guard")

    def test_legacy_log_shows_not_recorded(self):
        """A NULL value is shown plainly, not attributed to anyone."""
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url), "Not recorded")

    def test_no_fake_user_is_shown_for_a_legacy_log(self):
        """The legacy row must not borrow the other row's username."""
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"plate": "KA07HS5555"})
        self.assertContains(response, "KA07HS5555")
        self.assertContains(response, "Not recorded")
        self.assertNotContains(response, "hist_guard")

    def test_guard_can_see_the_column(self):
        self.client.force_login(self.guard)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recorded by")

    def test_resident_cannot_open_gate_history(self):
        """Role restrictions are unchanged by the new column."""
        self.client.force_login(self.resident_user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_is_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_filters_still_work_with_the_new_column(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"movement_type": "ENTRY"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MH66HS1234")

    def test_plate_search_still_works(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"plate": "mh 66 hs"})
        self.assertContains(response, "MH66HS1234")
        self.assertNotContains(response, "KA07HS5555")

    def test_gate_form_submission_appears_with_its_username(self):
        """End to end: record a movement, then see who recorded it."""
        self.client.force_login(self.guard)
        self.client.post(reverse("tracking:gate"), {
            "plate_number": "KA07HS7777", "movement_type": "ENTRY",
            "category": "UNKNOWN", "remarks": "",
        })
        response = self.client.get(self.url, {"plate": "KA07HS7777"})
        self.assertContains(response, "KA07HS7777")
        self.assertContains(response, "hist_guard")

    def test_the_page_does_not_query_once_per_row(self):
        """recorded_by must be joined, not fetched per row.

        Six queries regardless of how many rows are shown: session, user,
        two permission lookups, the paginator count, and one SELECT that
        LEFT JOINs auth_user for every row at once. Without select_related
        this would be six plus one per row.
        """
        for index in range(10):
            VehicleLog.objects.create(plate_number=f"KA07QQ{index:04d}",
                                      movement_type="ENTRY", recorded_by=self.guard)
        self.client.force_login(self.admin)
        with self.assertNumQueries(6):
            self.client.get(self.url)
