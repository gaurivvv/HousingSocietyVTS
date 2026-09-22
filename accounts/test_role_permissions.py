from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle

from .testing import make_user

ADMIN_ONLY = {"admin": 200, "guard": 403, "resident": 403}
ADMIN_AND_GUARD = {"admin": 200, "guard": 200, "resident": 403}


class RolePermissionTestData(TestCase):
    """Rajesh Sharma (A-101, phone 9876543210) owns MH12AB1234; one user per role."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        cls.car = Vehicle.objects.create(resident=cls.rajesh, vehicle_number="MH12AB1234", colour="White")
        cls.users = {role: make_user(role) for role in ["admin", "guard", "resident"]}

    def request_as(self, role, url, method="get", data=None):
        self.client.force_login(self.users[role])
        response = getattr(self.client, method)(url, data or {})
        self.client.logout()
        return response


class ResidentAndVehiclePagePermissionTests(RolePermissionTestData):
    def test_role_page_matrix(self):
        pages = [
            (reverse("residents:resident_list"), ADMIN_ONLY),
            (reverse("residents:resident_create"), ADMIN_ONLY),
            (reverse("residents:resident_update", args=[self.rajesh.pk]), ADMIN_ONLY),
            (reverse("vehicles:vehicle_list"), ADMIN_AND_GUARD),
            (reverse("vehicles:vehicle_create"), ADMIN_ONLY),
            (reverse("vehicles:vehicle_update", args=[self.car.pk]), ADMIN_ONLY),
        ]
        for url, expected in pages:
            for role, status in expected.items():
                with self.subTest(url=url, role=role):
                    self.assertEqual(self.request_as(role, url).status_code, status)

    def test_guard_cannot_add_a_resident_by_posting(self):
        before = Resident.objects.count()
        response = self.request_as(
            "guard", reverse("residents:resident_create"), "post",
            {"flat": self.rajesh.flat_id, "full_name": "Not Allowed", "resident_type": "OWNER", "phone": "9000000009"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Resident.objects.count(), before)

    def test_guard_cannot_edit_a_vehicle_by_posting(self):
        response = self.request_as(
            "guard", reverse("vehicles:vehicle_update", args=[self.car.pk]), "post",
            {"resident": self.rajesh.pk, "vehicle_number": "MH12AB1234", "vehicle_type": "FOUR_WHEELER", "colour": "Red"},
        )
        self.assertEqual(response.status_code, 403)
        self.car.refresh_from_db()
        self.assertEqual(self.car.colour, "White")


class VehiclePhoneSearchPrivacyTests(RolePermissionTestData):
    def search(self, role, query=""):
        return self.request_as(role, reverse("vehicles:vehicle_list"), data={"q": query} if query else None)

    def plates(self, response):
        return [vehicle.vehicle_number for vehicle in response.context["vehicles"]]

    def test_admin_can_find_a_vehicle_by_owner_phone(self):
        self.assertEqual(self.plates(self.search("admin", "9876543210")), ["MH12AB1234"])

    def test_guard_phone_search_matches_nothing(self):
        self.assertEqual(self.plates(self.search("guard", "9876543210")), [])

    def test_guard_can_still_search_by_plate_name_and_flat(self):
        for query in ["mh 12 ab", "rajesh", "A-101"]:
            with self.subTest(query=query):
                self.assertEqual(self.plates(self.search("guard", query)), ["MH12AB1234"])

    def test_placeholder_mentions_phone_only_for_admin(self):
        self.assertContains(self.search("admin"), "owner name, phone or flat (A-101)")
        guard_page = self.search("guard")
        self.assertContains(guard_page, "owner name or flat (A-101)")
        self.assertNotContains(guard_page, "phone or flat")

    def test_vehicle_table_never_shows_phone_numbers(self):
        for role in ["admin", "guard"]:
            with self.subTest(role=role):
                self.assertNotContains(self.search(role), "9876543210")
