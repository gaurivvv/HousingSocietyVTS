from django.urls import reverse

from tracking.models import VehicleLog
from visitors.models import Visitor

from .test_role_permissions import ADMIN_AND_GUARD, RolePermissionTestData


class GateAndVisitorPermissionTests(RolePermissionTestData):
    """Adds a visitor expected today (Amit Guest, visiting Rajesh) to the shared data."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.visitor = cls.new_visitor("Amit Guest", "9000000002")

    @classmethod
    def new_visitor(cls, name, phone):
        return Visitor.objects.create(full_name=name, phone=phone, flat=cls.rajesh.flat, resident=cls.rajesh)

    def status_of(self, visitor):
        visitor.refresh_from_db()
        return visitor.status

    def test_role_page_matrix(self):
        pages = [
            reverse("tracking:gate"),
            reverse("tracking:history"),
            reverse("visitors:visitor_list"),
            reverse("visitors:visitor_create"),
            reverse("visitors:visitor_detail", args=[self.visitor.pk]),
        ]
        for url in pages:
            for role, status in ADMIN_AND_GUARD.items():
                with self.subTest(url=url, role=role):
                    self.assertEqual(self.request_as(role, url).status_code, status)

    def test_guard_can_record_a_gate_movement(self):
        response = self.request_as(
            "guard", reverse("tracking:gate"), "post",
            {"plate_number": "MH12AB1234", "movement_type": "ENTRY", "category": "UNKNOWN", "remarks": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VehicleLog.objects.count(), 1)

    def test_resident_cannot_record_a_gate_movement(self):
        response = self.request_as(
            "resident", reverse("tracking:gate"), "post",
            {"plate_number": "MH12AB1234", "movement_type": "ENTRY", "category": "UNKNOWN", "remarks": ""},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(VehicleLog.objects.count(), 0)

    def test_resident_cannot_pre_register_a_visitor(self):
        before = Visitor.objects.count()
        response = self.request_as(
            "resident", reverse("visitors:visitor_create"), "post",
            {"full_name": "Not Allowed", "phone": "9000000009", "resident": self.rajesh.pk},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Visitor.objects.count(), before)

    def test_guard_can_check_in_check_out_and_cancel(self):
        self.request_as("guard", reverse("visitors:visitor_check_in", args=[self.visitor.pk]), "post")
        self.assertEqual(self.status_of(self.visitor), Visitor.Status.CHECKED_IN)

        self.request_as("guard", reverse("visitors:visitor_check_out", args=[self.visitor.pk]), "post")
        self.assertEqual(self.status_of(self.visitor), Visitor.Status.CHECKED_OUT)

        second = self.new_visitor("Neha Guest", "9000000003")
        self.request_as("guard", reverse("visitors:visitor_cancel", args=[second.pk]), "post")
        self.assertEqual(self.status_of(second), Visitor.Status.CANCELLED)

    def test_resident_cannot_use_visitor_actions(self):
        for name in ["visitor_check_in", "visitor_check_out", "visitor_cancel"]:
            with self.subTest(action=name):
                response = self.request_as("resident", reverse(f"visitors:{name}", args=[self.visitor.pk]), "post")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.status_of(self.visitor), Visitor.Status.EXPECTED)

    def test_permission_is_checked_before_the_method(self):
        url = reverse("visitors:visitor_check_in", args=[self.visitor.pk])
        # Resident: forbidden whatever the method
        self.assertEqual(self.request_as("resident", url).status_code, 403)
        # Guard (allowed): a GET is still refused as "method not allowed"
        self.assertEqual(self.request_as("guard", url).status_code, 405)
        self.assertEqual(self.status_of(self.visitor), Visitor.Status.EXPECTED)
