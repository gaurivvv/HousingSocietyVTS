from datetime import date, datetime, timedelta

from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle
from visitors.models import Visitor

from .models import VehicleLog


class VehicleLogVisitorLinkTests(TestCase):
    """Rajesh (A-101) owns MH12AB1234. Visitors are added per test."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.host = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"), full_name="Rajesh Sharma", phone="9876543210"
        )
        cls.car = Vehicle.objects.create(resident=cls.host, vehicle_number="MH12AB1234")

    def add_visitor(self, plate="MH14CD5678", days_from_today=0, **fields):
        data = {
            "full_name": "Amit Guest",
            "phone": "9000000002",
            "flat": self.host.flat,
            "resident": self.host,
            "vehicle_number": plate,
            "expected_date": timezone.localdate() + timedelta(days=days_from_today),
        }
        data.update(fields)
        return Visitor.objects.create(**data)

    def gate_entry(self, plate="MH14CD5678", **fields):
        return VehicleLog.objects.create(plate_number=plate, movement_type="ENTRY", **fields)

    # --- Matches ---

    def test_matches_todays_expected_visitor_without_changing_its_status(self):
        visitor = self.add_visitor()
        log = self.gate_entry(plate="mh 14-cd 5678")  # typed differently; normalized first

        self.assertEqual(log.visitor, visitor)
        self.assertEqual(log.category, VehicleLog.Category.VISITOR)
        self.assertIsNone(log.vehicle)
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.EXPECTED)  # not checked in automatically
        self.assertIsNone(visitor.entry_time)

    def test_matches_todays_checked_in_visitor_without_checking_it_out(self):
        visitor = self.add_visitor()
        visitor.check_in()
        log = VehicleLog.objects.create(plate_number="MH14CD5678", movement_type="EXIT")

        self.assertEqual(log.visitor, visitor)
        self.assertEqual(log.category, VehicleLog.Category.VISITOR)
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.CHECKED_IN)  # not checked out automatically
        self.assertIsNone(visitor.exit_time)

    def test_prefers_checked_in_visitor_when_two_match(self):
        self.add_visitor(full_name="Expected Guest")
        inside = self.add_visitor(full_name="Inside Guest", phone="9000000003")
        inside.check_in()
        self.assertEqual(self.gate_entry().visitor, inside)

    # --- No match ---

    def test_no_match_for_yesterday_or_a_future_date(self):
        for days in [-1, 1]:
            with self.subTest(days_from_today=days):
                visitor = self.add_visitor(days_from_today=days)
                log = self.gate_entry()
                self.assertIsNone(log.visitor)
                self.assertEqual(log.category, VehicleLog.Category.UNKNOWN)
                visitor.delete() if not visitor.gate_logs.exists() else None

    def test_no_match_for_expired_cancelled_or_checked_out_visitors(self):
        now = timezone.now()
        cases = [
            {"status": "EXPIRED"},
            {"status": "CANCELLED"},
            {"status": "CHECKED_OUT", "entry_time": now - timedelta(hours=2), "exit_time": now - timedelta(hours=1)},
        ]
        for fields in cases:
            with self.subTest(status=fields["status"]):
                plate = f"KA01{fields['status'][:2]}0001"
                self.add_visitor(plate=plate, **fields)
                log = self.gate_entry(plate=plate)
                self.assertIsNone(log.visitor)
                self.assertEqual(log.category, VehicleLog.Category.UNKNOWN)

    def test_registered_vehicle_takes_priority_over_visitor_data(self):
        self.add_visitor(plate="MH12AB1234")  # same plate as Rajesh's registered car
        log = self.gate_entry(plate="MH12AB1234")
        self.assertEqual(log.vehicle, self.car)
        self.assertEqual(log.category, VehicleLog.Category.REGISTERED)
        self.assertIsNone(log.visitor)

    def test_unknown_plate_stays_unknown_and_manual_visitor_is_kept(self):
        self.add_visitor()
        unknown = self.gate_entry(plate="DL01ZZ9999")
        self.assertIsNone(unknown.visitor)
        self.assertEqual(unknown.category, VehicleLog.Category.UNKNOWN)

        manual = self.gate_entry(plate="GJ05AB1111", category="VISITOR")
        self.assertIsNone(manual.visitor)
        self.assertEqual(manual.category, VehicleLog.Category.VISITOR)

    def test_visitor_on_foot_never_matches(self):
        self.add_visitor(plate="")
        log = self.gate_entry(plate="DL01ZZ9999")
        self.assertIsNone(log.visitor)

    # --- Dates use Indian time ---

    def test_match_uses_the_logs_indian_date(self):
        # 00:30 IST on 22 Sep is still 21 Sep in UTC; it must match the visitor expected on 22 Sep.
        self.add_visitor(plate="MH14CD0021", expected_date=date(2026, 9, 21))
        expected_22nd = self.add_visitor(plate="MH14CD0022", expected_date=date(2026, 9, 22), phone="9000000003")
        just_after_midnight = timezone.make_aware(datetime(2026, 9, 22, 0, 30))

        log_22nd = self.gate_entry(plate="MH14CD0022", timestamp=just_after_midnight)
        log_21st = self.gate_entry(plate="MH14CD0021", timestamp=just_after_midnight)

        self.assertEqual(log_22nd.visitor, expected_22nd)
        self.assertIsNone(log_21st.visitor)

    # --- Existing records and history ---

    def test_logs_without_visitor_still_work(self):
        log = self.gate_entry(plate="DL01ZZ9999")
        log.refresh_from_db()
        self.assertIsNone(log.visitor)
        log.full_clean()  # must not raise
        log.remarks = "Edited later"
        log.save()
        self.assertEqual(VehicleLog.objects.filter(visitor__isnull=True).count(), 1)
        self.assertIn("DL01ZZ9999", str(log))

    def test_visitor_with_gate_history_cannot_be_deleted(self):
        visitor = self.add_visitor()
        self.gate_entry()
        self.assertEqual(visitor.gate_logs.count(), 1)
        with self.assertRaises(ProtectedError):
            visitor.delete()

    def test_plate_edited_away_from_linked_visitor_is_rejected(self):
        self.add_visitor()
        log = self.gate_entry()
        log.plate_number = "DL01ZZ9999"
        with self.assertRaisesMessage(Exception, "does not match the linked visitor"):
            log.full_clean()
