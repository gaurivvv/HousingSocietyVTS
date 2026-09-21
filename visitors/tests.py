import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing

from .models import Visitor

PASS_CODE_PATTERN = r"VP-[A-HJ-NP-Z2-9]{6}"


class VisitorTestData(TestCase):
    """Shared data: Rajesh lives in A-101; A-102 has no residents."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.flat_101 = Flat.objects.create(wing=wing, flat_number="101")
        cls.flat_102 = Flat.objects.create(wing=wing, flat_number="102")
        cls.host = Resident.objects.create(flat=cls.flat_101, full_name="Rajesh Sharma", phone="9876543210")

    def new_visitor(self, **changes):
        """An unsaved visitor to Rajesh in A-101; each test changes only what it checks."""
        data = {"full_name": "Amit Guest", "phone": "9000000002", "flat": self.flat_101, "resident": self.host}
        data.update(changes)
        return Visitor(**data)

    def assert_errors(self, visitor, expected_fields):
        with self.assertRaises(ValidationError) as context:
            visitor.full_clean()
        self.assertEqual(sorted(context.exception.message_dict), sorted(expected_fields))


class VisitorModelTests(VisitorTestData):
    def test_defaults_and_normalization(self):
        visitor = self.new_visitor(full_name="  Amit   Guest ", vehicle_number="mh 14-cd 5678")
        visitor.save()
        self.assertEqual(visitor.full_name, "Amit Guest")
        self.assertEqual(visitor.vehicle_number, "MH14CD5678")
        self.assertEqual(visitor.status, Visitor.Status.EXPECTED)
        self.assertEqual(visitor.expected_date, timezone.localdate())
        self.assertIsNone(visitor.entry_time)
        self.assertIsNone(visitor.exit_time)

    def test_pass_code_is_generated_once_and_kept(self):
        visitor = self.new_visitor()
        visitor.save()
        self.assertRegex(visitor.pass_code, PASS_CODE_PATTERN)
        original_code = visitor.pass_code

        visitor.full_name = "Amit Kumar"
        visitor.save()
        visitor.refresh_from_db()
        self.assertEqual(visitor.pass_code, original_code)

    def test_pass_codes_are_unique(self):
        codes = set()
        for number in range(20):
            visitor = self.new_visitor(phone=f"90000001{number:02d}")
            visitor.save()
            codes.add(visitor.pass_code)
        self.assertEqual(len(codes), 20)

    def test_database_rejects_a_duplicate_pass_code(self):
        first = self.new_visitor()
        first.save()
        second = self.new_visitor(full_name="Neha Guest")
        second.pass_code = first.pass_code
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                second.save()

    def test_visitor_without_vehicle_is_valid(self):
        visitor = self.new_visitor()
        visitor.full_clean()
        visitor.save()
        self.assertEqual(visitor.vehicle_number, "")

    def test_too_short_vehicle_number_is_rejected(self):
        self.assert_errors(self.new_visitor(vehicle_number="AB"), ["vehicle_number"])

    def test_resident_must_live_in_the_flat_being_visited(self):
        self.assert_errors(self.new_visitor(flat=self.flat_102), ["resident"])

    def test_new_visit_for_inactive_resident_is_rejected(self):
        Resident.objects.filter(pk=self.host.pk).update(is_active=False)
        inactive_host = Resident.objects.get(pk=self.host.pk)
        self.assert_errors(self.new_visitor(resident=inactive_host), ["resident"])

    def test_existing_visit_stays_valid_after_resident_is_deactivated(self):
        visitor = self.new_visitor()
        visitor.save()
        Resident.objects.filter(pk=self.host.pk).update(is_active=False)
        Visitor.objects.get(pk=visitor.pk).full_clean()  # must not raise

    def test_status_must_match_entry_and_exit_times(self):
        now = timezone.now()
        cases = [
            ({"status": "CHECKED_IN"}, ["status"]),
            ({"status": "CHECKED_IN", "entry_time": now, "exit_time": now}, ["status"]),
            ({"status": "CHECKED_OUT", "exit_time": now}, ["exit_time", "status"]),
            ({"status": "CHECKED_OUT", "entry_time": now, "exit_time": now - timedelta(hours=1)}, ["exit_time"]),
            ({"status": "EXPECTED", "entry_time": now}, ["status"]),
            ({"status": "CANCELLED", "entry_time": now}, ["status"]),
            ({"status": "EXPIRED", "entry_time": now}, ["status"]),
        ]
        for fields, expected in cases:
            with self.subTest(fields=fields):
                self.assert_errors(self.new_visitor(**fields), expected)

    def test_valid_status_and_time_combinations(self):
        now = timezone.now()
        cases = [
            {"status": "EXPECTED"},
            {"status": "CANCELLED"},
            {"status": "EXPIRED"},
            {"status": "CHECKED_IN", "entry_time": now},
            {"status": "CHECKED_OUT", "entry_time": now - timedelta(hours=2), "exit_time": now},
        ]
        for fields in cases:
            with self.subTest(fields=fields):
                self.new_visitor(**fields).full_clean()  # must not raise

    def test_flat_and_resident_with_visitors_are_protected(self):
        visitor = self.new_visitor()
        visitor.save()
        with self.assertRaises(ProtectedError):
            self.host.delete()
        with self.assertRaises(ProtectedError) as context:
            self.flat_101.delete()
        self.assertIn(visitor, context.exception.protected_objects)


class VisitorAdminTests(VisitorTestData):
    def setUp(self):
        admin_user = get_user_model().objects.create_superuser(
            username="testadmin", password="Test-admin-pass-2026"
        )
        self.client.force_login(admin_user)

    def admin_form_data(self, **changes):
        data = {
            "full_name": "Amit Guest",
            "phone": "9000000002",
            "flat": str(self.flat_101.pk),
            "resident": str(self.host.pk),
            "vehicle_number": "",
            "expected_date": "2026-09-25",
            "status": "EXPECTED",
            "entry_time_0": "",
            "entry_time_1": "",
            "exit_time_0": "",
            "exit_time_1": "",
        }
        data.update(changes)
        return data

    def test_add_visitor_in_admin(self):
        response = self.client.post(
            reverse("admin:visitors_visitor_add"),
            self.admin_form_data(vehicle_number="mh 14 cd 5678"),
        )
        self.assertEqual(response.status_code, 302)
        visitor = Visitor.objects.get()
        self.assertEqual(visitor.vehicle_number, "MH14CD5678")
        self.assertRegex(visitor.pass_code, PASS_CODE_PATTERN)

    def test_admin_rejects_resident_from_another_flat(self):
        response = self.client.post(
            reverse("admin:visitors_visitor_add"),
            self.admin_form_data(flat=str(self.flat_102.pk)),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This resident does not live in the selected flat.")
        self.assertEqual(Visitor.objects.count(), 0)

    def test_search_by_pass_code_and_by_vehicle_number(self):
        with_car = self.new_visitor(vehicle_number="MH14CD5678")
        with_car.save()
        on_foot = self.new_visitor(full_name="Neha Guest", phone="9000000003")
        on_foot.save()
        list_url = reverse("admin:visitors_visitor_changelist")

        response = self.client.get(list_url, {"q": on_foot.pass_code})
        self.assertContains(response, "Neha Guest")
        self.assertNotContains(response, "Amit Guest")

        response = self.client.get(list_url, {"q": "mh-14-cd"})
        self.assertContains(response, "Amit Guest")
        self.assertNotContains(response, "Neha Guest")

    def test_status_filter(self):
        self.new_visitor().save()
        self.new_visitor(
            full_name="Neha Guest", phone="9000000003", status="CHECKED_IN", entry_time=timezone.now()
        ).save()
        response = self.client.get(reverse("admin:visitors_visitor_changelist"), {"status__exact": "CHECKED_IN"})
        self.assertContains(response, "Neha Guest")
        self.assertNotContains(response, "Amit Guest")

    def test_visitors_cannot_be_deleted_in_admin(self):
        visitor = self.new_visitor()
        visitor.save()
        response = self.client.get(reverse("admin:visitors_visitor_delete", args=[visitor.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Visitor.objects.filter(pk=visitor.pk).exists())
