from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing

from .models import Visitor


class VisitorActionsTestData(TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.host = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"), full_name="Rajesh Sharma", phone="9876543210"
        )

    def add_visitor(self, **fields):
        data = {"full_name": "Amit Guest", "phone": "9000000002", "flat": self.host.flat, "resident": self.host}
        data.update(fields)
        return Visitor.objects.create(**data)

    def tomorrow(self):
        return timezone.localdate() + timedelta(days=1)


class VisitorLifecycleModelTests(VisitorActionsTestData):
    def test_check_in_then_check_out(self):
        visitor = self.add_visitor()
        self.assertTrue(visitor.can_check_in)

        visitor.check_in()
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.CHECKED_IN)
        self.assertIsNotNone(visitor.entry_time)
        self.assertTrue(visitor.can_check_out)
        self.assertFalse(visitor.can_cancel)

        visitor.check_out()
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.CHECKED_OUT)
        self.assertGreaterEqual(visitor.exit_time, visitor.entry_time)
        self.assertFalse(visitor.can_check_in or visitor.can_check_out or visitor.can_cancel)

    def test_check_in_only_on_the_expected_date(self):
        visitor = self.add_visitor(expected_date=self.tomorrow())
        self.assertFalse(visitor.can_check_in)
        with self.assertRaisesMessage(ValidationError, "only be checked in on their expected date"):
            visitor.check_in()
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.EXPECTED)

    def test_cannot_check_in_twice(self):
        visitor = self.add_visitor()
        visitor.check_in()
        with self.assertRaisesMessage(ValidationError, "Only an expected visitor can be checked in"):
            visitor.check_in()

    def test_cannot_check_out_without_checking_in(self):
        visitor = self.add_visitor()
        with self.assertRaisesMessage(ValidationError, "Only a checked-in visitor can be checked out."):
            visitor.check_out()

    def test_cancel_only_before_arrival(self):
        visitor = self.add_visitor()
        visitor.cancel()
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.CANCELLED)
        self.assertIsNone(visitor.entry_time)
        with self.assertRaises(ValidationError):
            visitor.check_in()

        arrived = self.add_visitor(full_name="Neha Guest", phone="9000000003")
        arrived.check_in()
        with self.assertRaisesMessage(ValidationError, "Only an expected visitor can be cancelled."):
            arrived.cancel()


class VisitorActionPageTests(VisitorActionsTestData):
    def post_action(self, name, visitor, follow=True, **data):
        return self.client.post(reverse(f"visitors:{name}", args=[visitor.pk]), data, follow=follow)

    def test_check_in_button_returns_to_the_pass_page(self):
        visitor = self.add_visitor()
        response = self.post_action("visitor_check_in", visitor)
        self.assertRedirects(response, reverse("visitors:visitor_detail", args=[visitor.pk]))
        self.assertContains(response, f"Amit Guest checked in ({visitor.pass_code}).")
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.CHECKED_IN)

    def test_check_out_and_cancel_buttons(self):
        inside = self.add_visitor()
        inside.check_in()
        response = self.post_action("visitor_check_out", inside)
        self.assertContains(response, "Amit Guest checked out")

        expected = self.add_visitor(full_name="Neha Guest", phone="9000000003")
        response = self.post_action("visitor_cancel", expected)
        self.assertContains(response, "Visit by Neha Guest was cancelled")
        expected.refresh_from_db()
        self.assertEqual(expected.status, Visitor.Status.CANCELLED)

    def test_not_allowed_action_shows_error_and_changes_nothing(self):
        visitor = self.add_visitor()
        response = self.post_action("visitor_check_out", visitor)
        self.assertContains(response, "Only a checked-in visitor can be checked out.")
        self.assertContains(response, "alert-danger")
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.EXPECTED)

    def test_actions_require_post(self):
        visitor = self.add_visitor()
        response = self.client.get(reverse("visitors:visitor_check_in", args=[visitor.pk]))
        self.assertEqual(response.status_code, 405)
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Visitor.Status.EXPECTED)

    def test_returns_to_the_list_with_its_filters(self):
        visitor = self.add_visitor()
        list_url = reverse("visitors:visitor_list") + "?status=EXPECTED"
        response = self.post_action("visitor_check_in", visitor, follow=False, next=list_url)
        self.assertRedirects(response, list_url, fetch_redirect_response=False)

    def test_does_not_redirect_to_another_website(self):
        visitor = self.add_visitor()
        response = self.post_action("visitor_check_in", visitor, follow=False, next="https://evil.example.com/")
        self.assertRedirects(
            response, reverse("visitors:visitor_detail", args=[visitor.pk]), fetch_redirect_response=False
        )

    def test_missing_visitor_returns_404(self):
        response = self.client.post(reverse("visitors:visitor_check_in", args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_buttons_shown_only_when_allowed(self):
        today_visitor = self.add_visitor()
        later_visitor = self.add_visitor(full_name="Ravi Guest", phone="9000000004", expected_date=self.tomorrow())

        page = self.client.get(reverse("visitors:visitor_detail", args=[today_visitor.pk]))
        self.assertContains(page, reverse("visitors:visitor_check_in", args=[today_visitor.pk]))
        self.assertContains(page, reverse("visitors:visitor_cancel", args=[today_visitor.pk]))
        self.assertNotContains(page, reverse("visitors:visitor_check_out", args=[today_visitor.pk]))

        page = self.client.get(reverse("visitors:visitor_detail", args=[later_visitor.pk]))
        self.assertNotContains(page, reverse("visitors:visitor_check_in", args=[later_visitor.pk]))
        self.assertContains(page, "Check-in is available on the expected date only.")

        list_page = self.client.get(reverse("visitors:visitor_list"))
        self.assertContains(list_page, reverse("visitors:visitor_check_in", args=[today_visitor.pk]))
