"""Tests for the reports page.

Reports are society-wide analytics, restricted to Society Admin. Guards work
the gate and see individual movements; aggregate statistics across months are
a management function.

The visitor figures distinguish registered visits from arrivals, because a
booked visit may be cancelled, expire, or simply not happen.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.testing import make_user
from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle
from visitors.models import Visitor


class ReportsTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin", username="rep_admin")
        cls.guard = make_user("guard", username="rep_guard")
        cls.resident_user = make_user("resident", username="rep_resident")

        cls.today = timezone.localdate()
        cls.yesterday = cls.today - timedelta(days=1)
        cls.long_ago = cls.today - timedelta(days=90)

        wing = Wing.objects.create(name="P")
        flat = Flat.objects.create(wing=wing, flat_number="401")
        cls.resident = Resident.objects.create(
            flat=flat, full_name="Reports Testperson",
            resident_type="OWNER", phone="9000000004",
        )
        cls.vehicle = Vehicle.objects.create(
            resident=cls.resident, vehicle_number="MH55RP1234",
            vehicle_type="FOUR_WHEELER",
        )

        def log(plate, movement, when):
            moment = timezone.make_aware(
                timezone.datetime.combine(when, timezone.datetime.min.time())
            ) + timedelta(hours=10)
            return VehicleLog.objects.create(
                plate_number=plate, movement_type=movement, timestamp=moment
            )

        # Today: 2 entries (1 registered, 1 unknown), 1 exit
        log("MH55RP1234", "ENTRY", cls.today)
        log("KA09RP0001", "ENTRY", cls.today)
        log("MH55RP1234", "EXIT", cls.today)
        # Yesterday: 1 entry
        log("KA09RP0002", "ENTRY", cls.yesterday)
        # Outside the default range
        log("KA09RP0003", "ENTRY", cls.long_ago)

        # Visitors: registered is not the same as arrived
        Visitor.objects.create(
            full_name="Arrived Person", phone="9811111111", flat=flat,
            resident=cls.resident, expected_date=cls.today,
            entry_time=timezone.now(), status=Visitor.Status.CHECKED_IN,
        )
        Visitor.objects.create(
            full_name="Expected Person", phone="9822222222", flat=flat,
            resident=cls.resident, expected_date=cls.today,
            status=Visitor.Status.EXPECTED,
        )
        Visitor.objects.create(
            full_name="Cancelled Person", phone="9833333333", flat=flat,
            resident=cls.resident, expected_date=cls.yesterday,
            status=Visitor.Status.CANCELLED,
        )
        Visitor.objects.create(
            full_name="Old Person", phone="9844444444", flat=flat,
            resident=cls.resident, expected_date=cls.long_ago,
            status=Visitor.Status.EXPIRED,
        )

    def setUp(self):
        self.url = reverse("reports:reports")


class ReportAccessTests(ReportsTestBase):
    """Society-wide analytics are for administrators only."""

    def test_admin_can_open_reports(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_guard_is_forbidden(self):
        """Guards keep every existing permission; reports are simply not one."""
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_resident_is_forbidden(self):
        self.client.force_login(self.resident_user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_guard_still_reaches_the_gate_pages(self):
        """Adding reports must not narrow what a guard can already do."""
        self.client.force_login(self.guard)
        self.assertEqual(self.client.get(reverse("tracking:gate")).status_code, 200)
        self.assertEqual(self.client.get(reverse("tracking:history")).status_code, 200)

    def test_sidebar_link_hidden_from_a_guard(self):
        self.client.force_login(self.guard)
        self.assertNotContains(self.client.get(reverse("tracking:gate")), "reports:reports")


class GateReportTests(ReportsTestBase):
    """Movement totals come from database aggregation."""

    def test_default_range_counts_recent_movements_only(self):
        """The 90-day-old log is outside the default 30-day window."""
        self.client.force_login(self.admin)
        gate = self.client.get(self.url).context["gate"]
        self.assertEqual(gate["entries"], 3)
        self.assertEqual(gate["exits"], 1)
        self.assertEqual(gate["total"], 4)

    def test_registered_and_unknown_are_separated(self):
        self.client.force_login(self.admin)
        gate = self.client.get(self.url).context["gate"]
        self.assertEqual(gate["registered"], 2)
        self.assertEqual(gate["unknown"], 2)

    def test_daily_rows_are_grouped_by_date(self):
        self.client.force_login(self.admin)
        rows = self.client.get(self.url).context["gate_rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["day"], self.today)
        self.assertEqual(rows[0]["entries"], 2)
        self.assertEqual(rows[0]["exits"], 1)

    def test_explicit_range_includes_the_older_log(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {
            "start_date": self.long_ago.isoformat(),
            "end_date": self.today.isoformat(),
        })
        self.assertEqual(response.context["gate"]["total"], 5)

    def test_narrow_range_excludes_yesterday(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {
            "start_date": self.today.isoformat(),
            "end_date": self.today.isoformat(),
        })
        self.assertEqual(response.context["gate"]["total"], 3)

    def test_bar_widths_are_added(self):
        self.client.force_login(self.admin)
        rows = self.client.get(self.url).context["gate_rows"]
        self.assertEqual(rows[0]["bar_width"], 100)
        self.assertIn("bar_width", rows[1])


class VisitorReportTests(ReportsTestBase):
    """Registered is not the same as arrived."""

    def test_registered_and_arrived_differ(self):
        self.client.force_login(self.admin)
        visitors = self.client.get(self.url).context["visitors"]
        self.assertEqual(visitors["registered"], 3)
        self.assertEqual(visitors["arrived"], 1)

    def test_cancelled_and_expected_are_counted_separately(self):
        self.client.force_login(self.admin)
        visitors = self.client.get(self.url).context["visitors"]
        self.assertEqual(visitors["cancelled"], 1)
        self.assertEqual(visitors["expected"], 1)

    def test_a_cancelled_visit_is_not_counted_as_an_arrival(self):
        self.client.force_login(self.admin)
        visitors = self.client.get(self.url).context["visitors"]
        self.assertLess(visitors["arrived"], visitors["registered"])

    def test_daily_visitor_rows(self):
        self.client.force_login(self.admin)
        rows = self.client.get(self.url).context["visitor_rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["expected_date"], self.today)
        self.assertEqual(rows[0]["registered"], 2)
        self.assertEqual(rows[0]["arrived"], 1)


class ReportFilterValidationTests(ReportsTestBase):
    """Filters are validated on the server."""

    def test_end_before_start_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {
            "start_date": self.today.isoformat(),
            "end_date": self.long_ago.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must be on or after")

    def test_an_excessive_range_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {
            "start_date": (self.today - timedelta(days=400)).isoformat(),
            "end_date": self.today.isoformat(),
        })
        self.assertContains(response, "or fewer")

    def test_a_nonsense_date_does_not_crash(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {
            "start_date": "not-a-date", "end_date": "also-not-a-date",
        })
        self.assertEqual(response.status_code, 200)

    def test_invalid_filters_fall_back_to_the_default_range(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {
            "start_date": "not-a-date", "end_date": "nonsense",
        })
        self.assertFalse(response.context["filters_applied"])


class EmptyResultTests(ReportsTestBase):
    """A range with no data shows an empty state, not an error."""

    def test_future_range_is_empty(self):
        self.client.force_login(self.admin)
        future = self.today + timedelta(days=200)
        response = self.client.get(self.url, {
            "start_date": future.isoformat(),
            "end_date": (future + timedelta(days=10)).isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["gate"]["total"], 0)
        self.assertEqual(response.context["gate_rows"], [])

    def test_empty_range_shows_both_empty_states(self):
        self.client.force_login(self.admin)
        future = self.today + timedelta(days=200)
        response = self.client.get(self.url, {
            "start_date": future.isoformat(),
            "end_date": (future + timedelta(days=10)).isoformat(),
        })
        self.assertContains(response, "No gate movements in this date range.")
        self.assertContains(response, "No visitors expected in this date range.")


class AggregationEfficiencyTests(ReportsTestBase):
    """The page aggregates in the database rather than looping in Python."""

    def test_query_count_does_not_grow_with_the_data(self):
        for index in range(40):
            VehicleLog.objects.create(
                plate_number=f"KA09RR{index:04d}", movement_type="ENTRY"
            )
        self.client.force_login(self.admin)
        with self.assertNumQueries(8):
            self.client.get(self.url)
