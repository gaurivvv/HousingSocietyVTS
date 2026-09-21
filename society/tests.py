from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Flat, Wing

# The admin page for a wing also contains the "Flats" inline table.
# Django expects these hidden management fields for it on every submit.
NO_INLINE_FLATS = {
    "flats-TOTAL_FORMS": "0",
    "flats-INITIAL_FORMS": "0",
    "flats-MIN_NUM_FORMS": "0",
    "flats-MAX_NUM_FORMS": "1000",
}


class WingFlatAdminTests(TestCase):
    """Uses the Wing and Flat admin pages the same way a person would in the browser."""

    @classmethod
    def setUpTestData(cls):
        # A test-only admin account; it exists only in the temporary test database.
        cls.admin_user = get_user_model().objects.create_superuser(
            username="testadmin", password="Test-admin-pass-2026"
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    # Test 2: add a wing typed in lowercase
    def test_wing_name_is_saved_in_uppercase(self):
        response = self.client.post(
            reverse("admin:society_wing_add"),
            {"name": "a", "description": "", **NO_INLINE_FLATS},
        )
        self.assertEqual(response.status_code, 302)  # 302 = saved, redirected to the list
        self.assertTrue(Wing.objects.filter(name="A").exists())

    # Test 3: duplicate wing, typed differently
    def test_duplicate_wing_is_rejected(self):
        Wing.objects.create(name="A")
        response = self.client.post(
            reverse("admin:society_wing_add"),
            {"name": " a ", "description": "", **NO_INLINE_FLATS},
        )
        self.assertEqual(response.status_code, 200)  # 200 = form shown again with an error
        self.assertContains(response, "already exists")
        self.assertEqual(Wing.objects.count(), 1)

    # Test 4: add a flat inside the wing page (the inline table)
    def test_flat_can_be_added_from_the_wing_page(self):
        wing = Wing.objects.create(name="A")
        response = self.client.post(
            reverse("admin:society_wing_change", args=[wing.pk]),
            {
                "name": "A",
                "description": "",
                "flats-TOTAL_FORMS": "1",
                "flats-INITIAL_FORMS": "0",
                "flats-MIN_NUM_FORMS": "0",
                "flats-MAX_NUM_FORMS": "1000",
                "flats-0-id": "",
                "flats-0-wing": str(wing.pk),
                "flats-0-flat_number": "102",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Flat.objects.filter(wing=wing, flat_number="102").exists())

    # Test 5: duplicate flat in the same wing
    def test_duplicate_flat_is_rejected(self):
        wing = Wing.objects.create(name="A")
        Flat.objects.create(wing=wing, flat_number="101")
        response = self.client.post(
            reverse("admin:society_flat_add"),
            {"wing": str(wing.pk), "flat_number": "101"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(Flat.objects.count(), 1)

    # Test 6: flats list shows A-101 style names; filter and search work
    def test_flat_list_filter_and_search(self):
        wing_a = Wing.objects.create(name="A")
        wing_b = Wing.objects.create(name="B")
        Flat.objects.create(wing=wing_a, flat_number="101")
        Flat.objects.create(wing=wing_a, flat_number="102")
        Flat.objects.create(wing=wing_b, flat_number="201")
        list_url = reverse("admin:society_flat_changelist")

        response = self.client.get(list_url)
        self.assertContains(response, "A-101")
        self.assertContains(response, "A-102")

        response = self.client.get(list_url, {"wing__id__exact": wing_a.pk})
        self.assertContains(response, "A-101")
        self.assertNotContains(response, "B-201")

        response = self.client.get(list_url, {"q": "102"})
        self.assertContains(response, "A-102")
        self.assertNotContains(response, "A-101")

    # Test 7: a wing that still has flats cannot be deleted
    def test_wing_with_flats_cannot_be_deleted(self):
        wing = Wing.objects.create(name="A")
        Flat.objects.create(wing=wing, flat_number="101")
        response = self.client.post(
            reverse("admin:society_wing_changelist"),
            {"action": "delete_selected", "_selected_action": [wing.pk], "post": "yes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "protected")
        self.assertTrue(Wing.objects.filter(pk=wing.pk).exists())