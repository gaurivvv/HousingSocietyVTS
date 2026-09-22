from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from accounts.roles import RESIDENT
from accounts.testing import TEST_PASSWORD, make_user
from society.models import Flat, Wing

from .forms import ResidentForm
from .models import Resident


class ResidentAdminUserLinkTests(TestCase):
    """Rajesh (A-101) and Priya (A-102) are unlinked; one eligible and several ineligible logins exist."""

    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        cls.flat_101 = Flat.objects.create(wing=wing, flat_number="101")
        cls.flat_102 = Flat.objects.create(wing=wing, flat_number="102")
        cls.rajesh = Resident.objects.create(flat=cls.flat_101, full_name="Rajesh Sharma", phone="9876543210")
        cls.priya = Resident.objects.create(flat=cls.flat_102, full_name="Priya Patil", phone="9123456780")

        cls.eligible = make_user("resident", username="asha_login")
        cls.guard = make_user("guard", username="guard_login")
        cls.society_admin = make_user("admin", username="society_admin_login")
        cls.superuser_login = User.objects.create_superuser(username="super_login", password=TEST_PASSWORD)
        cls.staff_in_resident_group = make_user("resident", username="staff_resident_login")
        cls.staff_in_resident_group.is_staff = True
        cls.staff_in_resident_group.save()
        cls.no_group_login = User.objects.create_user(username="no_group_login", password=TEST_PASSWORD)

        # A superuser that is NOT staff but IS in the Resident group must still be excluded
        cls.hidden_superuser = User.objects.create_user(
            username="hidden_super_login", password=TEST_PASSWORD, is_superuser=True, is_staff=False
        )
        cls.hidden_superuser.groups.add(Group.objects.get(name=RESIDENT))

        cls.site_owner = User.objects.create_superuser(username="site_owner", password=TEST_PASSWORD)

    def setUp(self):
        self.client.force_login(self.site_owner)

    def change_url(self, resident):
        return reverse("admin:residents_resident_change", args=[resident.pk])

    def offered_logins(self, resident):
        form = self.client.get(self.change_url(resident)).context["adminform"].form
        return list(form.fields["user"].queryset)

    def save_with_login(self, resident, login):
        data = {
            "flat": resident.flat_id,
            "user": login.pk if login else "",
            "full_name": resident.full_name,
            "resident_type": resident.resident_type,
            "phone": resident.phone,
            "email": resident.email,
            "is_active": "on",
        }
        return self.client.post(self.change_url(resident), data)

    def test_only_the_eligible_login_is_offered(self):
        self.assertEqual(self.offered_logins(self.rajesh), [self.eligible])

    def test_eligible_login_can_be_linked(self):
        response = self.save_with_login(self.rajesh, self.eligible)
        self.assertEqual(response.status_code, 302)
        self.rajesh.refresh_from_db()
        self.assertEqual(self.rajesh.user, self.eligible)
        self.assertEqual(User.objects.get(pk=self.eligible.pk).resident, self.rajesh)

    def test_linked_login_shows_in_the_admin_list_and_search(self):
        self.save_with_login(self.rajesh, self.eligible)
        list_url = reverse("admin:residents_resident_changelist")

        response = self.client.get(list_url)
        self.assertContains(response, "asha_login")

        response = self.client.get(list_url, {"q": "asha_login"})
        self.assertContains(response, "Rajesh Sharma")
        self.assertNotContains(response, "Priya Patil")

    def test_link_can_be_cleared(self):
        self.save_with_login(self.rajesh, self.eligible)
        response = self.save_with_login(self.rajesh, None)
        self.assertEqual(response.status_code, 302)
        self.rajesh.refresh_from_db()
        self.assertIsNone(self.rajesh.user)
        self.assertTrue(User.objects.filter(pk=self.eligible.pk).exists())

    def test_ineligible_logins_are_rejected_on_save(self):
        ineligible = {
            "guard": self.guard,
            "society admin (staff)": self.society_admin,
            "superuser": self.superuser_login,
            "staff in Resident group": self.staff_in_resident_group,
            "superuser in Resident group, not staff": self.hidden_superuser,
            "no group, not staff": self.no_group_login,
        }
        for label, login in ineligible.items():
            with self.subTest(login=label):
                self.assertNotIn(login, self.offered_logins(self.rajesh))
                response = self.save_with_login(self.rajesh, login)
                self.assertEqual(response.status_code, 200)
                self.assertIn("user", response.context["adminform"].form.errors)
                self.rajesh.refresh_from_db()
                self.assertIsNone(self.rajesh.user)

    def test_login_linked_to_another_resident_is_not_offered_but_stays_for_its_own_resident(self):
        self.save_with_login(self.priya, self.eligible)
        self.assertNotIn(self.eligible, self.offered_logins(self.rajesh))
        self.assertIn(self.eligible, self.offered_logins(self.priya))

    def test_website_form_still_has_no_user_field(self):
        self.assertNotIn("user", ResidentForm().fields)
        response = self.client.get(reverse("residents:resident_create"))
        self.assertNotContains(response, 'name="user"')
