from django.test import TestCase
from accounts.testing import LoggedInAsSocietyAdminMixin
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing

from .models import Vehicle


class VehicleCreatePageTests(LoggedInAsSocietyAdminMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        cls.former_tenant = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="102"),
            full_name="Former Tenant",
            phone="9123456780",
            is_active=False,
        )

    def form_data(self, **changes):
        data = {
            "resident": str(self.rajesh.pk),
            "vehicle_number": "MH12AB1234",
            "vehicle_type": "FOUR_WHEELER",
            "model_name": "",
            "colour": "",
        }
        data.update(changes)
        return data

    def post_form(self, **changes):
        return self.client.post(reverse("vehicles:vehicle_create"), self.form_data(**changes))

    def test_add_page_loads_and_list_links_to_it(self):
        response = self.client.get(reverse("vehicles:vehicle_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "vehicles/vehicle_form.html")
        self.assertContains(response, "Rajesh Sharma (A-101)")
        list_page = self.client.get(reverse("vehicles:vehicle_list"))
        self.assertContains(list_page, reverse("vehicles:vehicle_create"))

    def test_valid_form_registers_vehicle_with_normalized_plate(self):
        response = self.client.post(
            reverse("vehicles:vehicle_create"),
            self.form_data(vehicle_number="mh 12-ab 1234", model_name=" Honda City ", colour="White"),
            follow=True,
        )
        self.assertRedirects(response, reverse("vehicles:vehicle_list"))
        self.assertContains(response, "Vehicle MH12AB1234 was registered to Rajesh Sharma.")
        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.vehicle_number, "MH12AB1234")
        self.assertEqual(vehicle.resident, self.rajesh)
        self.assertEqual(vehicle.model_name, "Honda City")
        self.assertTrue(vehicle.is_active)

    def test_invalid_plate_is_rejected(self):
        response = self.post_form(vehicle_number="ABC123")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid Indian vehicle number")
        self.assertEqual(Vehicle.objects.count(), 0)

    def test_duplicate_plate_typed_differently_is_rejected(self):
        Vehicle.objects.create(resident=self.rajesh, vehicle_number="MH12AB1234")
        response = self.post_form(vehicle_number="MH-12-AB-1234")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This vehicle number is already registered.")
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_inactive_resident_cannot_be_chosen_as_owner(self):
        response = self.client.get(reverse("vehicles:vehicle_create"))
        self.assertNotContains(response, "Former Tenant")

        response = self.post_form(resident=str(self.former_tenant.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn("resident", response.context["form"].errors)
        self.assertEqual(Vehicle.objects.count(), 0)

    def test_empty_form_shows_required_errors(self):
        response = self.client.post(reverse("vehicles:vehicle_create"), {})
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        for field in ["resident", "vehicle_number"]:
            self.assertIn(field, form.errors)
        self.assertEqual(Vehicle.objects.count(), 0)
