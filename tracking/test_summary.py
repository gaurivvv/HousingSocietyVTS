from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import VehicleLog
from .utils import todays_counts, vehicles_inside


class GateSummaryTests(TestCase):
    def log(self, plate, movement, minutes_ago):
        return VehicleLog.objects.create(
            plate_number=plate,
            movement_type=movement,
            timestamp=timezone.now() - timedelta(minutes=minutes_ago),
        )

    def inside_plates(self):
        return [log.plate_number for log in vehicles_inside()]

    def test_vehicle_is_inside_only_when_latest_movement_is_entry(self):
        self.log("KA01AA0001", "ENTRY", 30)
        self.log("KA01BB0002", "ENTRY", 20)
        self.log("KA01BB0002", "EXIT", 10)
        self.assertEqual(self.inside_plates(), ["KA01AA0001"])

    def test_vehicle_that_comes_back_is_inside_again_once(self):
        self.log("KA01CC0003", "ENTRY", 30)
        self.log("KA01CC0003", "EXIT", 20)
        self.log("KA01CC0003", "ENTRY", 10)
        self.assertEqual(self.inside_plates(), ["KA01CC0003"])

    def test_exit_without_entry_is_not_inside(self):
        self.log("KA01DD0004", "EXIT", 5)
        self.assertEqual(self.inside_plates(), [])

    def test_todays_counts_ignore_earlier_days(self):
        self.log("KA01EE0005", "ENTRY", 60 * 24 * 2)  # two days ago
        self.log("KA01EE0005", "ENTRY", 3)
        self.log("KA01FF0006", "ENTRY", 2)
        self.log("KA01FF0006", "EXIT", 1)
        self.assertEqual(todays_counts(), {"entries": 2, "exits": 1})

    def test_gate_page_shows_summary_and_inside_list(self):
        self.log("KA01GG0007", "ENTRY", 5)
        response = self.client.get(reverse("tracking:gate"))
        self.assertEqual(len(response.context["inside_logs"]), 1)
        self.assertEqual(response.context["today"], {"entries": 1, "exits": 0})
        self.assertContains(response, "Vehicles inside now")
        self.assertContains(response, "KA01GG0007")

    def test_gate_page_with_nobody_inside(self):
        response = self.client.get(reverse("tracking:gate"))
        self.assertContains(response, "No vehicles are inside right now.")
