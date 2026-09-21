from django.test import TestCase
from django.urls import reverse

from residents.models import Resident
from society.models import Flat, Wing

from .models import Vehicle


class VehicleEditPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        cls.priya = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="102"),
            full_name="Priya Patil",
            phone="9123456780",
        )
        cls.car = Vehicle.objects.create(
            resident=cls.rajesh,
            vehicle_number="MH12AB1234",
            model_name="Honda City",
            colour="White",
        )
        cls.scooter = Vehicle.objects.create(
            resident=cls.priya,
            vehicle_number="MH14CD5678",
            vehicle_type=Vehicle.VehicleType.TWO_WHEELER,
        )

    def edit_url(self, vehicle):
        return reverse("vehicles:vehicle_update", args=[vehicle.pk])

    def form_data(self, **changes):
        # The car's current details; each test changes only what it checks
        data = {
            "resident": str(self.rajesh.pk),
            "vehicle_number": "MH12AB1234",
            "vehicle_type": "FOUR_WHEELER",
            "model_name": "Honda City",
            "colour": "White",
        }
        data.update(changes)
        return data

    def test_edit_page_shows_current_values(self):
        response = self.client.get(self.edit_url(self.car))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "vehicles/vehicle_form.html")
        self.assertContains(response, "Edit Vehicle")
        self.assertContains(response, 'value="MH12AB1234"')
        self.assertEqual(response.context["form"].initial["resident"], self.rajesh.pk)

    def test_list_page_links_to_edit_page(self):
        response = self.client.get(reverse("vehicles:vehicle_list"))
        self.assertContains(response, self.edit_url(self.car))

    def test_update_saves_changes_and_shows_message(self):
        response = self.client.post(
            self.edit_url(self.car),
            self.form_data(colour="Black", model_name="Honda Amaze"),
            follow=True,
        )
        self.assertRedirects(response, reverse("vehicles:vehicle_list"))
        self.assertContains(response, "Vehicle MH12AB1234 was updated.")
        self.car.refresh_from_db()
        self.assertEqual(self.car.colour, "Black")
        self.assertEqual(self.car.model_name, "Honda Amaze")
        self.assertEqual(Vehicle.objects.count(), 2)  # updated, not duplicated

    def test_vehicle_can_be_transferred_to_another_resident(self):
        response = self.client.post(self.edit_url(self.car), self.form_data(resident=str(self.priya.pk)))
        self.assertEqual(response.status_code, 302)
        self.car.refresh_from_db()
        self.assertEqual(self.car.resident, self.priya)

    def test_saving_without_changes_is_not_a_duplicate(self):
        response = self.client.post(self.edit_url(self.car), self.form_data())
        self.assertEqual(response.status_code, 302)

    def test_cannot_change_plate_to_another_vehicles_plate(self):
        response = self.client.post(self.edit_url(self.car), self.form_data(vehicle_number="mh-14-cd-5678"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This vehicle number is already registered.")
        self.car.refresh_from_db()
        self.assertEqual(self.car.vehicle_number, "MH12AB1234")

    def test_vehicle_of_inactive_owner_can_still_be_edited(self):
        Resident.objects.filter(pk=self.rajesh.pk).update(is_active=False)

        response = self.client.get(self.edit_url(self.car))
        self.assertContains(response, "Rajesh Sharma (A-101)")

        response = self.client.post(self.edit_url(self.car), self.form_data(colour="Silver"))
        self.assertEqual(response.status_code, 302)
        self.car.refresh_from_db()
        self.assertEqual(self.car.colour, "Silver")

    def test_missing_vehicle_returns_404(self):
        response = self.client.get(reverse("vehicles:vehicle_update", args=[99999]))
        self.assertEqual(response.status_code, 404)
