from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle
from visitors.models import Visitor

from .testing import make_user

UNLINKED_MESSAGE = "Your login isn't linked to a resident record yet. Please contact the society office."
INACTIVE_MESSAGE = "Your resident record is inactive. Please contact the society office."

ASHA_DETAILS = ["Asha Kulkarni", "A-101", "9811111111", "asha@example.com"]
RAVI_DETAILS = ["Ravi Menon", "B-202", "9822222222", "ravi@example.com"]


class ResidentMyAccountTests(TestCase):
    """Asha (A-101, owner) and Ravi (B-202, tenant) each have their own linked login."""

    @classmethod
    def setUpTestData(cls):
        flat_a101 = Flat.objects.create(wing=Wing.objects.create(name="A"), flat_number="101")
        flat_b202 = Flat.objects.create(wing=Wing.objects.create(name="B"), flat_number="202")
        cls.asha_login = make_user("resident", username="asha_login")
        cls.ravi_login = make_user("resident", username="ravi_login")
        cls.asha = Resident.objects.create(
            flat=flat_a101, full_name="Asha Kulkarni", resident_type="OWNER",
            phone="9811111111", email="asha@example.com", user=cls.asha_login,
        )
        cls.ravi = Resident.objects.create(
            flat=flat_b202, full_name="Ravi Menon", resident_type="TENANT",
            phone="9822222222", email="ravi@example.com", user=cls.ravi_login,
        )
        # Asha's own vehicle, visitor and gate log: none of these belong on My Account (Step 7b)
        Vehicle.objects.create(resident=cls.asha, vehicle_number="MH12AB1234")
        Visitor.objects.create(
            full_name="Guest Sunil", phone="9833333333", flat=flat_a101,
            resident=cls.asha, vehicle_number="MH14CD5678",
        )
        VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="ENTRY")

    def page_as(self, login):
        self.client.force_login(login)
        return self.client.get(reverse("accounts:my_account"))

    def assert_none_of(self, response, texts):
        for text in texts:
            with self.subTest(must_not_contain=text):
                self.assertNotContains(response, text)

    def test_anonymous_user_is_redirected_to_login(self):
        me_url = reverse("accounts:my_account")
        response = self.client.get(me_url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={me_url}")

    def test_active_resident_sees_their_own_details(self):
        response = self.page_as(self.asha_login)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["portal_state"], "active")
        self.assertEqual(response.context["resident"], self.asha)
        for text in ASHA_DETAILS + ["Owner", "Active"]:
            with self.subTest(must_contain=text):
                self.assertContains(response, text)
        self.assertInHTML("<span>A</span>", response.content.decode())  # the wing

    def test_resident_never_sees_another_residents_details(self):
        self.assert_none_of(self.page_as(self.asha_login), RAVI_DETAILS + ["Tenant"])
        self.client.logout()
        self.assert_none_of(self.page_as(self.ravi_login), ASHA_DETAILS + ["Owner"])

    def test_unlinked_resident_login_sees_only_the_unlinked_message(self):
        response = self.page_as(make_user("resident", username="not_linked_login"))
        self.assertEqual(response.context["portal_state"], "unlinked")
        self.assertIsNone(response.context["resident"])
        self.assertContains(response, UNLINKED_MESSAGE)
        self.assert_none_of(response, ASHA_DETAILS + RAVI_DETAILS)

    def test_inactive_resident_sees_only_the_inactive_message(self):
        Resident.objects.filter(pk=self.asha.pk).update(is_active=False)
        response = self.page_as(self.asha_login)
        self.assertEqual(response.context["portal_state"], "inactive")
        self.assertIsNone(response.context["resident"])
        self.assertContains(response, INACTIVE_MESSAGE)
        self.assert_none_of(response, ASHA_DETAILS + [UNLINKED_MESSAGE])

    def test_guard_and_society_admin_get_no_resident_data(self):
        for role in ["guard", "admin"]:
            with self.subTest(role=role):
                response = self.page_as(make_user(role, username=f"me_{role}"))
                self.assertEqual(response.context["portal_state"], "unlinked")
                self.assertContains(response, UNLINKED_MESSAGE)
                self.assert_none_of(response, ASHA_DETAILS + RAVI_DETAILS)
                self.client.logout()

    def test_page_has_no_vehicles_visitors_gate_history_or_actions(self):
        response = self.page_as(self.asha_login)
        self.assert_none_of(response, [
            "MH12AB1234", "MH14CD5678", "Guest Sunil",   # vehicle, visitor, gate log plates
            "/edit/", "/residents/", "/vehicles/", "/visitors/", "/gate/", "/admin/",
            "Check in", "Check out", "Cancel visit", "Record a gate movement",
        ])

    def test_resident_is_found_only_through_the_link_not_matching_email(self):
        # Asha's login is given Ravi's email: the page must still show Asha (the linked resident)
        self.asha_login.email = "ravi@example.com"
        self.asha_login.save()
        response = self.page_as(self.asha_login)
        self.assertEqual(response.context["resident"], self.asha)
        self.assertContains(response, "Asha Kulkarni")
        self.assert_none_of(response, ["Ravi Menon", "B-202", "9822222222"])

    def test_unlinked_login_matching_another_residents_details_gets_nothing(self):
        # Username = Ravi's phone, email = Ravi's email, first name = Ravi, but NOT linked
        lookalike = make_user("resident", username="9822222222")
        lookalike.email = "ravi@example.com"
        lookalike.first_name = "Ravi"
        lookalike.last_name = "Menon"
        lookalike.save()
        response = self.page_as(lookalike)
        self.assertEqual(response.context["portal_state"], "unlinked")
        self.assertIsNone(response.context["resident"])
        self.assert_none_of(response, ["B-202", "ravi@example.com", "Tenant"])
