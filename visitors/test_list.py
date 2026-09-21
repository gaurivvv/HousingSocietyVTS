from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing

from .models import Visitor


class VisitorListPageTests(TestCase):
    """Today: Amit (car, expected) and Neha (on foot, checked in).
    Tomorrow: Ravi (expected). Two days ago: Old Guest (expired)."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"), full_name="Rajesh Sharma", phone="9876543210"
        )
        priya = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="102"), full_name="Priya Patil", phone="9123456780"
        )
        today = timezone.localdate()

        def add(name, phone, resident, **fields):
            return Visitor.objects.create(
                full_name=name, phone=phone, resident=resident, flat=resident.flat, **fields
            )

        cls.amit = add("Amit Guest", "9000000002", rajesh, vehicle_number="MH14CD5678")
        cls.neha = add("Neha Guest", "9000000003", priya, status="CHECKED_IN", entry_time=timezone.now())
        cls.ravi = add("Ravi Guest", "9000000004", rajesh, expected_date=today + timedelta(days=1))
        cls.old = add("Old Guest", "9000000005", rajesh, expected_date=today - timedelta(days=2), status="EXPIRED")

    def get_list(self, **params):
        return self.client.get(reverse("visitors:visitor_list"), params)

    def names(self, response):
        return sorted(visitor.full_name for visitor in response.context["page_obj"])

    def test_shows_todays_visitors_by_default(self):
        response = self.get_list()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "visitors/visitor_list.html")
        self.assertEqual(self.names(response), ["Amit Guest", "Neha Guest"])
        self.assertEqual(response.context["filter_form"]["date"].value(), timezone.localdate().isoformat())

    def test_empty_date_shows_all_dates(self):
        response = self.get_list(date="")
        self.assertEqual(self.names(response), ["Amit Guest", "Neha Guest", "Old Guest", "Ravi Guest"])

    def test_filter_by_another_date(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        response = self.get_list(date=tomorrow.isoformat())
        self.assertEqual(self.names(response), ["Ravi Guest"])

    def test_search_by_pass_code(self):
        response = self.get_list(date="", q=self.neha.pass_code.lower())
        self.assertEqual(self.names(response), ["Neha Guest"])

    def test_search_by_vehicle_number_typed_differently(self):
        response = self.get_list(date="", q="mh-14-cd")
        self.assertEqual(self.names(response), ["Amit Guest"])

    def test_search_by_resident_name_and_by_flat(self):
        self.assertEqual(self.names(self.get_list(date="", q="priya")), ["Neha Guest"])
        self.assertEqual(self.names(self.get_list(date="", q="a-102")), ["Neha Guest"])

    def test_filter_by_status(self):
        response = self.get_list(date="", status="CHECKED_IN")
        self.assertEqual(self.names(response), ["Neha Guest"])

    def test_rows_show_visit_details(self):
        response = self.get_list()
        for text in [self.amit.pass_code, "Rajesh Sharma", "A-101", "MH14CD5678", "On foot", "Expected", "Checked in"]:
            self.assertContains(response, text)
        self.assertContains(response, reverse("visitors:visitor_detail", args=[self.amit.pk]))

    def test_no_matches_message(self):
        response = self.get_list(q="nobody")
        self.assertContains(response, "No visitors found for these filters.")

    def test_page_links_keep_the_date(self):
        response = self.get_list(status="EXPECTED")
        self.assertIn("date=" + timezone.localdate().isoformat(), response.context["query_string"])
        self.assertIn("status=EXPECTED", response.context["query_string"])

    def test_invalid_date_does_not_crash(self):
        response = self.get_list(date="2026-13-40")
        self.assertEqual(response.status_code, 200)
        self.assertIn("date", response.context["filter_form"].errors)

    def test_navbar_links_to_visitors_and_highlights_it(self):
        home = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertInHTML('<a class="nav-link" href="/visitors/">Visitors</a>', home)
        page = self.get_list().content.decode()
        self.assertInHTML('<a class="nav-link active" href="/visitors/">Visitors</a>', page)
