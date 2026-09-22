from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing
from visitors.models import Visitor

from .models import VehicleLog


class VehicleLogAdminVisitorTests(TestCase):
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

    def setUp(self):
        admin_user = get_user_model().objects.create_superuser(username="testadmin", password="Test-admin-pass-2026")
        self.client.force_login(admin_user)
        self.list_url = reverse("admin:tracking_vehiclelog_changelist")

    def test_list_shows_the_visitor_and_the_host(self):
        VehicleLog.objects.create(plate_number="MH14CD5678", movement_type="ENTRY")
        response = self.client.get(self.list_url)
        self.assertContains(response, str(self.visitor))
        self.assertContains(response, "Owner / host")
        self.assertContains(response, "Rajesh Sharma")

    def test_search_by_visitor_name_and_pass_code(self):
        VehicleLog.objects.create(plate_number="MH14CD5678", movement_type="ENTRY")
        VehicleLog.objects.create(plate_number="DL01ZZ9999", movement_type="ENTRY")

        for term in ["amit", self.visitor.pass_code]:
            with self.subTest(search=term):
                response = self.client.get(self.list_url, {"q": term})
                self.assertContains(response, "MH14CD5678")
                self.assertNotContains(response, "DL01ZZ9999")

    def test_visitor_is_read_only_on_the_edit_page(self):
        log = VehicleLog.objects.create(plate_number="MH14CD5678", movement_type="ENTRY")
        response = self.client.get(reverse("admin:tracking_vehiclelog_change", args=[log.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.visitor))
        self.assertNotContains(response, 'name="visitor"')

    def test_adding_in_admin_links_the_visitor_automatically(self):
        response = self.client.post(
            reverse("admin:tracking_vehiclelog_add"),
            {
                "plate_number": "mh 14 cd 5678",
                "movement_type": "ENTRY",
                "category": "UNKNOWN",
                "timestamp_0": self.visitor.expected_date.isoformat(),
                "timestamp_1": "10:30:00",
                "remarks": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        log = VehicleLog.objects.get()
        self.assertEqual(log.visitor, self.visitor)
        self.assertEqual(log.category, VehicleLog.Category.VISITOR)
        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.status, Visitor.Status.EXPECTED)
