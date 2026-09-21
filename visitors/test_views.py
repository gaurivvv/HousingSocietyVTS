from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing

from .models import Visitor


class VisitorPagesTestData(TestCase):
    """Rajesh (active) lives in A-101; a former tenant (inactive) lived in A-102."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.flat_101 = Flat.objects.create(wing=wing, flat_number="101")
        cls.host = Resident.objects.create(flat=cls.flat_101, full_name="Rajesh Sharma", phone="9876543210")
        cls.former = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="102"),
            full_name="Former Tenant",
            phone="9123456780",
            is_active=False,
        )


class VisitorCreatePageTests(VisitorPagesTestData):
    def form_data(self, **changes):
        data = {
            "full_name": "Amit Guest",
            "phone": "9000000002",
            "resident": str(self.host.pk),
            "vehicle_number": "",
            "expected_date": timezone.localdate().isoformat(),
        }
        data.update(changes)
        return data

    def post_form(self, follow=False, **changes):
        return self.client.post(reverse("visitors:visitor_create"), self.form_data(**changes), follow=follow)

    def test_add_page_lists_only_active_residents_with_their_flat(self):
        response = self.client.get(reverse("visitors:visitor_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "visitors/visitor_form.html")
        self.assertContains(response, "Rajesh Sharma (A-101)")
        self.assertNotContains(response, "Former Tenant")
        self.assertEqual(response.context["form"]["expected_date"].value(), timezone.localdate())

    def test_valid_pre_registration_shows_the_pass(self):
        response = self.post_form(
            follow=True, full_name="  Amit   Guest ", phone="+91 90000 00002", vehicle_number="mh 14-cd 5678"
        )
        visitor = Visitor.objects.get()
        self.assertRedirects(response, reverse("visitors:visitor_detail", args=[visitor.pk]))
        self.assertContains(response, f"Visitor Amit Guest was pre-registered. Pass code: {visitor.pass_code}")
        self.assertEqual(visitor.flat, self.flat_101)
        self.assertEqual(visitor.resident, self.host)
        self.assertEqual(visitor.phone, "9000000002")
        self.assertEqual(visitor.vehicle_number, "MH14CD5678")
        self.assertEqual(visitor.status, Visitor.Status.EXPECTED)

    def test_visitor_on_foot(self):
        response = self.post_form()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Visitor.objects.get().vehicle_number, "")

    def test_future_date_is_allowed_but_past_date_is_rejected(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.assertEqual(self.post_form(expected_date=tomorrow.isoformat()).status_code, 302)

        yesterday = timezone.localdate() - timedelta(days=1)
        response = self.post_form(full_name="Neha Guest", expected_date=yesterday.isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The expected date cannot be in the past.")
        self.assertEqual(Visitor.objects.count(), 1)

    def test_invalid_phone_and_short_vehicle_are_rejected(self):
        response = self.post_form(phone="12345")
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone", response.context["form"].errors)

        response = self.post_form(vehicle_number="AB")
        self.assertContains(response, "Enter the full vehicle number, or leave it empty.")
        self.assertEqual(Visitor.objects.count(), 0)

    def test_inactive_resident_cannot_be_chosen(self):
        response = self.post_form(resident=str(self.former.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn("resident", response.context["form"].errors)
        self.assertEqual(Visitor.objects.count(), 0)

    def test_empty_form_shows_required_errors(self):
        response = self.client.post(reverse("visitors:visitor_create"), {})
        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        for field in ["full_name", "phone", "resident"]:
            self.assertIn(field, errors)
        self.assertEqual(Visitor.objects.count(), 0)


class VisitorDetailPageTests(VisitorPagesTestData):
    def test_pass_page_shows_code_and_visit_details(self):
        visitor = Visitor.objects.create(
            full_name="Amit Guest", phone="9000000002", flat=self.flat_101,
            resident=self.host, vehicle_number="MH14CD5678",
        )
        response = self.client.get(reverse("visitors:visitor_detail", args=[visitor.pk]))
        self.assertEqual(response.status_code, 200)
        for text in [visitor.pass_code, "Amit Guest", "Rajesh Sharma", "A-101", "MH14CD5678", "Expected"]:
            self.assertContains(response, text)

    def test_pass_page_for_visitor_on_foot(self):
        visitor = Visitor.objects.create(
            full_name="Walk In", phone="9000000003", flat=self.flat_101, resident=self.host
        )
        response = self.client.get(reverse("visitors:visitor_detail", args=[visitor.pk]))
        self.assertContains(response, "On foot")

    def test_missing_visitor_returns_404(self):
        response = self.client.get(reverse("visitors:visitor_detail", args=[99999]))
        self.assertEqual(response.status_code, 404)
