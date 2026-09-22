from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog

from .models import Visitor


class VisitorPassGateMovementsTests(TestCase):
    """Rajesh (A-101) expects Amit Guest today in MH14CD5678."""

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

    def pass_page(self, visitor):
        return self.client.get(reverse("visitors:visitor_detail", args=[visitor.pk]))

    def test_lists_the_visitors_movements_in_the_order_they_happened(self):
        now = timezone.now()
        entry = VehicleLog.objects.create(
            plate_number="MH14CD5678", movement_type="ENTRY", timestamp=now - timedelta(minutes=30)
        )
        exit_log = VehicleLog.objects.create(
            plate_number="MH14CD5678", movement_type="EXIT", timestamp=now - timedelta(minutes=5)
        )
        response = self.pass_page(self.visitor)

        self.assertContains(response, "Vehicle movements at the gate")
        self.assertEqual(list(response.context["gate_logs"]), [entry, exit_log])
        self.assertContains(response, "Entry")
        self.assertContains(response, "Exit")

    def test_message_when_no_movements_yet(self):
        response = self.pass_page(self.visitor)
        self.assertContains(response, "No gate movements recorded for this vehicle yet.")

    def test_other_vehicles_are_not_listed(self):
        VehicleLog.objects.create(plate_number="DL01ZZ9999", movement_type="ENTRY")
        response = self.pass_page(self.visitor)
        self.assertEqual(list(response.context["gate_logs"]), [])
        self.assertNotContains(response, "DL01ZZ9999")

    def test_visitor_on_foot_has_no_movements_card(self):
        walk_in = Visitor.objects.create(
            full_name="Walk In", phone="9000000003", flat=self.host.flat, resident=self.host
        )
        response = self.pass_page(walk_in)
        self.assertNotContains(response, "Vehicle movements at the gate")

    def test_viewing_movements_does_not_change_the_visitor_status(self):
        VehicleLog.objects.create(plate_number="MH14CD5678", movement_type="ENTRY")
        self.pass_page(self.visitor)
        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.status, Visitor.Status.EXPECTED)
        self.assertIsNone(self.visitor.entry_time)
