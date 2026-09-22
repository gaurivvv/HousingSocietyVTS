from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle
from visitors.models import Visitor

from .models import VehicleLog


class GateHistoryVisitorDisplayTests(TestCase):
    """One registered movement, one visitor movement and one unknown movement."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.host = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"), full_name="Rajesh Sharma", phone="9876543210"
        )
        Vehicle.objects.create(resident=cls.host, vehicle_number="MH12AB1234")
        cls.visitor = Visitor.objects.create(
            full_name="Amit Guest", phone="9000000002", flat=cls.host.flat,
            resident=cls.host, vehicle_number="MH14CD5678",
        )
        cls.registered_log = VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="ENTRY")
        cls.visitor_log = VehicleLog.objects.create(plate_number="MH14CD5678", movement_type="ENTRY")
        cls.unknown_log = VehicleLog.objects.create(plate_number="DL01ZZ9999", movement_type="ENTRY")

    def test_history_shows_the_visitor_and_who_they_are_visiting(self):
        self.assertEqual(self.visitor_log.visitor, self.visitor)
        response = self.client.get(reverse("tracking:history"))
        self.assertContains(response, "Owner / Visitor")
        self.assertContains(response, "Amit Guest")
        self.assertContains(response, "visiting Rajesh Sharma (A-101)")

    def test_registered_and_unknown_rows_are_unchanged(self):
        response = self.client.get(reverse("tracking:history"), {"plate": "MH12AB1234"})
        self.assertContains(response, "Rajesh Sharma")
        self.assertNotContains(response, "visiting")

        response = self.client.get(reverse("tracking:history"), {"plate": "DL01ZZ9999"})
        self.assertNotContains(response, "visiting")
        self.assertNotContains(response, "Amit Guest")

    def test_visitor_filter_lists_the_linked_visitor(self):
        response = self.client.get(reverse("tracking:history"), {"category": "VISITOR"})
        plates = [log.plate_number for log in response.context["page_obj"]]
        self.assertEqual(plates, ["MH14CD5678"])
        self.assertContains(response, "visiting Rajesh Sharma (A-101)")
