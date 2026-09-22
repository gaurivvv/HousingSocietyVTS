from django.test import TestCase
from accounts.testing import LoggedInAsSocietyAdminMixin
from django.urls import reverse


class GateHistoryLinkTests(LoggedInAsSocietyAdminMixin, TestCase):
    def html(self, url_name):
        return self.client.get(reverse(url_name)).content.decode()

    def test_navbar_links_to_gate_history_on_every_page(self):
        history_url = reverse("tracking:history")
        for url_name in ["dashboard:home", "residents:resident_list", "vehicles:vehicle_list", "tracking:gate"]:
            with self.subTest(page=url_name):
                self.assertIn(history_url, self.html(url_name))

    def test_gate_page_links_to_full_history(self):
        self.assertInHTML(
            '<a href="/gate/history/" class="small">View full history</a>',
            self.html("tracking:gate"),
        )

    def test_only_gate_is_highlighted_on_gate_page(self):
        page = self.html("tracking:gate")
        self.assertInHTML('<a class="nav-link active" href="/gate/">Gate</a>', page)
        self.assertInHTML('<a class="nav-link" href="/gate/history/">Gate History</a>', page)

    def test_only_gate_history_is_highlighted_on_history_page(self):
        page = self.html("tracking:history")
        self.assertInHTML('<a class="nav-link active" href="/gate/history/">Gate History</a>', page)
        self.assertInHTML('<a class="nav-link" href="/gate/">Gate</a>', page)
