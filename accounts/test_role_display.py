from django.urls import reverse

from .test_role_permissions import RolePermissionTestData

NAV_LINKS = {
    "Home": '<a class="nav-link" href="/">Home</a>',
    "Residents": '<a class="nav-link" href="/residents/">Residents</a>',
    "Vehicles": '<a class="nav-link" href="/vehicles/">Vehicles</a>',
    "Gate": '<a class="nav-link" href="/gate/">Gate</a>',
    "Gate History": '<a class="nav-link" href="/gate/history/">Gate History</a>',
    "Visitors": '<a class="nav-link" href="/visitors/">Visitors</a>',
    "Django Admin": '<a class="nav-link" href="/admin/">Django Admin</a>',
}

EXPECTED_NAV = {
    "admin": {"Home", "Residents", "Vehicles", "Gate", "Gate History", "Visitors", "Django Admin"},
    "guard": {"Home", "Vehicles", "Gate", "Gate History", "Visitors"},
    "resident": {"Home"},
}

QUICK_LINKS = {
    "Record a gate movement": ("/gate/", "Record a gate movement"),
    "View today's visitors": ("/visitors/", "View today&#x27;s visitors"),
    "View residents": ("/residents/", "View residents"),
    "Add a resident": ("/residents/add/", "Add a resident"),
    "View vehicles": ("/vehicles/", "View vehicles"),
    "Register a vehicle": ("/vehicles/add/", "Register a vehicle"),
    "Django Admin": ("/admin/", "Django Admin (wings and flats)"),
}


def quick_link_html(name):
    href, text = QUICK_LINKS[name]
    return f'<a href="{href}" class="list-group-item list-group-item-action">{text}</a>'


class NavbarPerRoleTests(RolePermissionTestData):
    def test_each_role_sees_exactly_its_navbar_links(self):
        for role, expected in EXPECTED_NAV.items():
            html = self.request_as(role, reverse("accounts:my_account")).content.decode()
            for name, link in NAV_LINKS.items():
                with self.subTest(role=role, link=name):
                    self.assertInHTML(link, html, count=1 if name in expected else 0)

    def test_logged_out_login_page_shows_no_staff_links(self):
        html = self.client.get(reverse("accounts:login")).content.decode()
        for name, link in NAV_LINKS.items():
            with self.subTest(link=name):
                self.assertInHTML(link, html, count=0)
        self.assertInHTML('<a class="nav-link" href="/accounts/login/">Log in</a>', html)


class HomeQuickLinksPerRoleTests(RolePermissionTestData):
    def test_society_admin_sees_every_quick_link(self):
        html = self.request_as("admin", reverse("dashboard:home")).content.decode()
        for name in QUICK_LINKS:
            with self.subTest(link=name):
                self.assertInHTML(quick_link_html(name), html, count=1)

    def test_guard_sees_only_gate_visitor_and_vehicle_list_links(self):
        html = self.request_as("guard", reverse("dashboard:home")).content.decode()
        allowed = {"Record a gate movement", "View today's visitors", "View vehicles"}
        for name in QUICK_LINKS:
            with self.subTest(link=name):
                self.assertInHTML(quick_link_html(name), html, count=1 if name in allowed else 0)

    def test_guard_still_sees_the_society_totals(self):
        response = self.request_as("guard", reverse("dashboard:home"))
        for label in ["Wings", "Flats", "Active Residents", "Active Vehicles", "Vehicles inside now"]:
            with self.subTest(label=label):
                self.assertContains(response, label)


class VehicleListButtonsPerRoleTests(RolePermissionTestData):
    def test_society_admin_sees_add_and_edit(self):
        response = self.request_as("admin", reverse("vehicles:vehicle_list"))
        self.assertContains(response, "Add Vehicle")
        self.assertContains(response, reverse("vehicles:vehicle_update", args=[self.car.pk]))
        self.assertContains(response, ">Actions</th>")

    def test_guard_sees_the_list_without_add_edit_or_actions_column(self):
        response = self.request_as("guard", reverse("vehicles:vehicle_list"))
        self.assertContains(response, "MH12AB1234")
        self.assertNotContains(response, "Add Vehicle")
        self.assertNotContains(response, reverse("vehicles:vehicle_update", args=[self.car.pk]))
        self.assertNotContains(response, ">Actions</th>")
