from django.test import TestCase
from accounts.testing import LoggedInAsSocietyAdminMixin
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing
from visitors.models import Visitor

from .models import VehicleLog


class GatePageVisitorDisplayTests(LoggedInAsSocietyAdminMixin, TestCase):
    """Rajesh (A-101) expects Amit Guest today, arriving in MH14CD5678."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.host = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"), full_name="Rajesh Sharma", phone="9876543210"
        )
        cls.visitor = Visitor.objects.create(
            full_name="Amit Guest", phone="9000000002", flat=cls.host.flat,
            resident=cls.host, vehicle_number="MH14CD5678",
        )

    def record(self, **changes):
        data = {"plate_number": "MH14CD5678", "movement_type": "ENTRY", "category": "UNKNOWN", "remarks": ""}
        data.update(changes)
        return self.client.post(reverse("tracking:gate"), data, follow=True)

    def test_message_names_the_matched_visitor(self):
        response = self.record(plate_number="mh 14-cd 5678")
        self.assertContains(
            response,
            "Entry recorded for MH14CD5678: visitor Amit Guest, visiting Rajesh Sharma (A-101).",
        )
        self.assertContains(response, "alert-success")
        self.assertEqual(VehicleLog.objects.get().visitor, self.visitor)

    def test_tables_show_the_visitor_and_who_they_are_visiting(self):
        self.record()
        response = self.client.get(reverse("tracking:gate"))
        self.assertEqual(len(response.context["inside_logs"]), 1)
        # Once in Recent movements and once in Vehicles inside now
        self.assertContains(response, "visiting Rajesh Sharma (A-101)", count=2)
        self.assertContains(response, "Owner / Visitor", count=2)

    def test_recording_at_the_gate_does_not_change_the_visitor_status(self):
        self.record()
        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.status, Visitor.Status.EXPECTED)
        self.assertIsNone(self.visitor.entry_time)

    def test_manual_visitor_without_match_keeps_the_old_message(self):
        response = self.record(plate_number="GJ05AB1111", category="VISITOR")
        self.assertContains(response, "Entry recorded for GJ05AB1111: visitor vehicle.")
        self.assertNotContains(response, "visiting Rajesh Sharma")
