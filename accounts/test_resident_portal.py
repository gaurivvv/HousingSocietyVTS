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
NO_VEHICLES_MESSAGE = "You don't have any registered vehicles."

ASHA_DETAILS = ["Asha Kulkarni", "A-101", "9811111111", "asha@example.com"]
RAVI_DETAILS = ["Ravi Menon", "B-202", "9822222222", "ravi@example.com"]

ASHA_PLATES = ["MH12AB1234", "MH12CD5678"]
RAVI_PLATE = "KA05GH4321"
MEERA_PLATE = "MH12EF9999"   # Meera lives in the SAME flat as Asha (A-101)
ALL_PLATES = ASHA_PLATES + [RAVI_PLATE, MEERA_PLATE]


class ResidentPortalTestData(TestCase):
    """Asha (A-101, owner) and Ravi (B-202, tenant) each have their own linked login.
    Meera also lives in A-101 and has her own login and vehicle."""

    @classmethod
    def setUpTestData(cls):
        flat_a101 = Flat.objects.create(wing=Wing.objects.create(name="A"), flat_number="101")
        flat_b202 = Flat.objects.create(wing=Wing.objects.create(name="B"), flat_number="202")
        cls.flat_b202 = flat_b202
        cls.asha_login = make_user("resident", username="asha_login")
        cls.ravi_login = make_user("resident", username="ravi_login")
        cls.meera_login = make_user("resident", username="meera_login")
        cls.asha = Resident.objects.create(
            flat=flat_a101, full_name="Asha Kulkarni", resident_type="OWNER",
            phone="9811111111", email="asha@example.com", user=cls.asha_login,
        )
        cls.ravi = Resident.objects.create(
            flat=flat_b202, full_name="Ravi Menon", resident_type="TENANT",
            phone="9822222222", email="ravi@example.com", user=cls.ravi_login,
        )
        cls.meera = Resident.objects.create(
            flat=flat_a101, full_name="Meera Kulkarni", resident_type="OWNER",
            phone="9844444444", email="meera@example.com", user=cls.meera_login,
        )
        # Asha's vehicles (one active, one inactive); Ravi's and Meera's vehicles
        Vehicle.objects.create(resident=cls.asha, vehicle_number="MH12AB1234",
                               vehicle_type="FOUR_WHEELER", model_name="Swift", colour="White")
        Vehicle.objects.create(resident=cls.asha, vehicle_number="MH12CD5678", vehicle_type="TWO_WHEELER",
                               model_name="Activa", colour="Grey", is_active=False)
        Vehicle.objects.create(resident=cls.ravi, vehicle_number=RAVI_PLATE,
                               vehicle_type="FOUR_WHEELER", model_name="City", colour="Blue")
        Vehicle.objects.create(resident=cls.meera, vehicle_number=MEERA_PLATE,
                               vehicle_type="FOUR_WHEELER", model_name="Nexon", colour="Red")
        # Asha's visitor and a gate log: neither belongs on this page
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

    def plates(self, response):
        return [vehicle.vehicle_number for vehicle in response.context["vehicles"]]


class ResidentMyAccountTests(ResidentPortalTestData):
    """Step 7b: the My Account section."""

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

    def test_page_has_no_visitors_gate_history_or_actions(self):
        # Step 7c: the resident's OWN vehicles are now shown, so their plate is no longer
        # checked here; gate history, visitors and actions must still never appear.
        response = self.page_as(self.asha_login)
        self.assert_none_of(response, [
            "MH14CD5678", "Guest Sunil",                 # visitor
            "Entry", "Gate History",                     # gate history
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
        self.assert_none_of(response, ["B-202", "ravi@example.com", "Tenant", RAVI_PLATE])


class ResidentMyVehiclesTests(ResidentPortalTestData):
    """Step 7c: the My Vehicles section."""

    def test_active_resident_sees_all_and_only_their_own_vehicles(self):
        response = self.page_as(self.asha_login)
        self.assertContains(response, "My Vehicles")
        self.assertEqual(self.plates(response), ["MH12AB1234", "MH12CD5678"])  # ordered by number
        for plate in ASHA_PLATES:
            with self.subTest(plate=plate):
                self.assertContains(response, plate)

    def test_vehicle_rows_show_number_type_model_colour_and_status(self):
        response = self.page_as(self.asha_login)
        for text in ["Vehicle Number", "Vehicle Type", "Model", "Colour", "Status",
                     "Four Wheeler", "Swift", "White", "Two Wheeler", "Activa", "Grey", "Inactive"]:
            with self.subTest(must_contain=text):
                self.assertContains(response, text)

    def test_other_residents_vehicles_never_appear_even_in_the_same_flat(self):
        self.assert_none_of(self.page_as(self.asha_login), [RAVI_PLATE, MEERA_PLATE])  # other flat, same flat
        self.client.logout()
        self.assert_none_of(self.page_as(self.meera_login), ASHA_PLATES)                # same flat, other way round
        self.client.logout()
        self.assert_none_of(self.page_as(self.ravi_login), ASHA_PLATES + [MEERA_PLATE])

    def test_unlinked_login_sees_no_vehicles(self):
        response = self.page_as(make_user("resident", username="not_linked_login"))
        self.assertIsNone(response.context["vehicles"])
        self.assert_none_of(response, ALL_PLATES + ["My Vehicles", NO_VEHICLES_MESSAGE])

    def test_inactive_resident_sees_no_vehicles(self):
        Resident.objects.filter(pk=self.asha.pk).update(is_active=False)
        response = self.page_as(self.asha_login)
        self.assertIsNone(response.context["vehicles"])
        self.assertContains(response, INACTIVE_MESSAGE)
        self.assert_none_of(response, ALL_PLATES + ["My Vehicles"])

    def test_guard_and_society_admin_see_no_vehicles(self):
        for role in ["guard", "admin"]:
            with self.subTest(role=role):
                response = self.page_as(make_user(role, username=f"vehicles_{role}"))
                self.assertIsNone(response.context["vehicles"])
                self.assert_none_of(response, ALL_PLATES + ["My Vehicles"])
                self.client.logout()

    def test_no_vehicle_management_actions(self):
        response = self.page_as(self.asha_login)
        self.assert_none_of(response, ["Add Vehicle", "Register a vehicle", "Edit", "Delete",
                                       "Transfer", "/vehicles/", "/admin/"])

    def test_resident_without_vehicles_sees_the_empty_message(self):
        kiran_login = make_user("resident", username="kiran_login")
        Resident.objects.create(flat=self.flat_b202, full_name="Kiran Rao", phone="9855555555", user=kiran_login)
        response = self.page_as(kiran_login)
        self.assertEqual(self.plates(response), [])
        self.assertContains(response, NO_VEHICLES_MESSAGE)
        self.assert_none_of(response, ALL_PLATES)

    def test_vehicles_follow_the_link_not_matching_login_details(self):
        # Asha's login gets Ravi's email; a look-alike login copies Ravi's phone/email/name.
        self.asha_login.email = "ravi@example.com"
        self.asha_login.save()
        response = self.page_as(self.asha_login)
        self.assertEqual(self.plates(response), ASHA_PLATES)
        self.assertNotContains(response, RAVI_PLATE)
        self.client.logout()

        lookalike = make_user("resident", username="9822222222")
        lookalike.email = "ravi@example.com"
        lookalike.first_name, lookalike.last_name = "Ravi", "Menon"
        lookalike.save()
        response = self.page_as(lookalike)
        self.assertIsNone(response.context["vehicles"])
        self.assertNotContains(response, RAVI_PLATE)
