from datetime import date, datetime, timedelta, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing

from .models import Visitor


class ExpireVisitorsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.host = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"), full_name="Rajesh Sharma", phone="9876543210"
        )

    def add_visitor(self, name, days_from_today, **fields):
        """A visitor expected N days from today (negative = in the past)."""
        return Visitor.objects.create(
            full_name=name,
            phone="9000000002",
            flat=self.host.flat,
            resident=self.host,
            expected_date=timezone.localdate() + timedelta(days=days_from_today),
            **fields,
        )

    def run_command(self):
        output = StringIO()
        call_command("expire_visitors", stdout=output)
        return output.getvalue()

    def status_of(self, visitor):
        visitor.refresh_from_db()
        return visitor.status

    def test_expires_only_expected_visitors_from_earlier_dates(self):
        three_days_ago = self.add_visitor("Three Days Ago", -3)
        yesterday = self.add_visitor("Yesterday Guest", -1)
        today = self.add_visitor("Today Guest", 0)
        tomorrow = self.add_visitor("Tomorrow Guest", 1)

        output = self.run_command()

        self.assertEqual(self.status_of(three_days_ago), Visitor.Status.EXPIRED)
        self.assertEqual(self.status_of(yesterday), Visitor.Status.EXPIRED)
        self.assertEqual(self.status_of(today), Visitor.Status.EXPECTED)
        self.assertEqual(self.status_of(tomorrow), Visitor.Status.EXPECTED)
        today_text = timezone.localdate().strftime("%d %b %Y")
        self.assertIn(f"Expired 2 visitors expected before {today_text}.", output)

    def test_other_statuses_are_never_changed(self):
        now = timezone.now()
        checked_in = self.add_visitor("Inside Guest", -1, status="CHECKED_IN", entry_time=now - timedelta(days=1))
        checked_out = self.add_visitor(
            "Left Guest", -1, status="CHECKED_OUT",
            entry_time=now - timedelta(days=1, hours=2), exit_time=now - timedelta(days=1),
        )
        cancelled = self.add_visitor("Cancelled Guest", -1, status="CANCELLED")
        already_expired = self.add_visitor("Old Guest", -5, status="EXPIRED")

        output = self.run_command()

        self.assertEqual(self.status_of(checked_in), Visitor.Status.CHECKED_IN)
        self.assertEqual(self.status_of(checked_out), Visitor.Status.CHECKED_OUT)
        self.assertEqual(self.status_of(cancelled), Visitor.Status.CANCELLED)
        self.assertEqual(self.status_of(already_expired), Visitor.Status.EXPIRED)
        self.assertIsNotNone(checked_in.entry_time)
        self.assertIsNotNone(checked_out.exit_time)
        self.assertIn("No visitors to expire", output)

    def test_no_visitors_at_all(self):
        output = self.run_command()
        today_text = timezone.localdate().strftime("%d %b %Y")
        self.assertIn(f"No visitors to expire (no expected visits before {today_text}).", output)

    def test_one_visitor_uses_singular_wording(self):
        self.add_visitor("Yesterday Guest", -1)
        self.assertIn("Expired 1 visitor expected before", self.run_command())

    def test_running_twice_expires_nothing_the_second_time(self):
        self.add_visitor("Yesterday Guest", -1)
        self.assertIn("Expired 1 visitor", self.run_command())
        self.assertIn("No visitors to expire", self.run_command())

    def test_expired_records_stay_valid_and_updated_at_changes(self):
        visitor = self.add_visitor("Yesterday Guest", -1)
        before = visitor.updated_at

        self.run_command()

        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.EXPIRED)
        self.assertIsNone(visitor.entry_time)
        self.assertIsNone(visitor.exit_time)
        self.assertGreater(visitor.updated_at, before)
        visitor.full_clean()  # every model rule still passes

    def test_uses_indian_date_not_utc_date(self):
        # 19:00 UTC on 21 Sep is 00:30 IST on 22 Sep: in India it is already the 22nd.
        common = {"phone": "9000000002", "flat": self.host.flat, "resident": self.host}
        visit_on_21st = Visitor.objects.create(full_name="Visit On 21st", expected_date=date(2026, 9, 21), **common)
        visit_on_22nd = Visitor.objects.create(full_name="Visit On 22nd", expected_date=date(2026, 9, 22), **common)

        fake_now = datetime(2026, 9, 21, 19, 0, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=fake_now):
            output = self.run_command()

        self.assertEqual(self.status_of(visit_on_21st), Visitor.Status.EXPIRED)
        self.assertEqual(self.status_of(visit_on_22nd), Visitor.Status.EXPECTED)
        self.assertIn("expected before 22 Sep 2026.", output)
