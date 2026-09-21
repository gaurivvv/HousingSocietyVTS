from datetime import datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing
from vehicles.models import Vehicle

from .models import VehicleLog


def at(year, month, day, hour, minute=0):
    """An exact date and time in the project's time zone (Asia/Kolkata)."""
    return timezone.make_aware(datetime(year, month, day, hour, minute))


class GateHistoryPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wing = Wing.objects.create(name="A")
        rajesh = Resident.objects.create(
            flat=Flat.objects.create(wing=wing, flat_number="101"),
            full_name="Rajesh Sharma",
            phone="9876543210",
        )
        Vehicle.objects.create(resident=rajesh, vehicle_number="MH12AB1234")

        # 20 Sep: registered car enters, unknown van enters
        VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="ENTRY", timestamp=at(2026, 9, 20, 9))
        VehicleLog.objects.create(plate_number="KA01XY0001", movement_type="ENTRY", timestamp=at(2026, 9, 20, 18))
        # 21 Sep: visitor leaves, registered car leaves
        VehicleLog.objects.create(
            plate_number="GJ05AB1111", movement_type="EXIT", category="VISITOR", timestamp=at(2026, 9, 21, 11)
        )
        VehicleLog.objects.create(plate_number="MH12AB1234", movement_type="EXIT", timestamp=at(2026, 9, 21, 12))

    def get_history(self, **params):
        return self.client.get(reverse("tracking:history"), params)

    def plates(self, response):
        return [log.plate_number for log in response.context["page_obj"]]

    def test_history_page_shows_all_logs_with_details(self):
        response = self.get_history()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tracking/history.html")
        self.assertEqual(response.context["total_count"], 4)
        for text in ["MH12AB1234", "KA01XY0001", "GJ05AB1111", "Rajesh Sharma", "A-101",
                     "Registered", "Visitor", "Unknown", "Entry", "Exit", "20 Sep 2026, 09:00"]:
            self.assertContains(response, text)

    def test_newest_movement_is_listed_first(self):
        response = self.get_history()
        self.assertEqual(self.plates(response), ["MH12AB1234", "GJ05AB1111", "KA01XY0001", "MH12AB1234"])

    def test_more_than_twenty_logs_are_available_across_pages(self):
        start = at(2026, 9, 22, 8)
        for number in range(30):
            VehicleLog.objects.create(
                plate_number=f"KA02ZZ{number:04d}", movement_type="ENTRY", timestamp=start + timedelta(minutes=number)
            )
        response = self.get_history()
        self.assertEqual(response.context["total_count"], 34)
        self.assertEqual(len(response.context["page_obj"]), 25)

        response = self.get_history(page=2)
        self.assertEqual(len(response.context["page_obj"]), 9)

    def test_plate_search_is_normalized(self):
        response = self.get_history(plate="mh 12-ab")
        self.assertEqual(self.plates(response), ["MH12AB1234", "MH12AB1234"])

    def test_filter_by_date_range(self):
        response = self.get_history(date_from="2026-09-21", date_to="2026-09-21")
        self.assertEqual(self.plates(response), ["MH12AB1234", "GJ05AB1111"])

        response = self.get_history(date_to="2026-09-20")
        self.assertEqual(self.plates(response), ["KA01XY0001", "MH12AB1234"])

    def test_date_filter_uses_indian_time(self):
        # 00:30 on 21 Sep in India is still 20 Sep in UTC; it must count as 21 Sep.
        VehicleLog.objects.create(plate_number="DL01AA0001", movement_type="ENTRY", timestamp=at(2026, 9, 21, 0, 30))
        self.assertIn("DL01AA0001", self.plates(self.get_history(date_from="2026-09-21")))
        self.assertNotIn("DL01AA0001", self.plates(self.get_history(date_to="2026-09-20")))

    def test_filter_by_movement_and_category(self):
        response = self.get_history(movement_type="EXIT")
        self.assertEqual(self.plates(response), ["MH12AB1234", "GJ05AB1111"])

        response = self.get_history(category="VISITOR")
        self.assertEqual(self.plates(response), ["GJ05AB1111"])

    def test_invalid_date_range_shows_error(self):
        response = self.get_history(date_from="2026-09-21", date_to="2026-09-20")
        self.assertEqual(response.status_code, 200)
        self.assertIn("date_to", response.context["filter_form"].errors)
        self.assertContains(response, "The &#x27;to&#x27; date must be on or after the &#x27;from&#x27; date.")

    def test_impossible_date_does_not_crash(self):
        response = self.get_history(date_from="2026-13-40")
        self.assertEqual(response.status_code, 200)
        self.assertIn("date_from", response.context["filter_form"].errors)

    def test_no_matches_message_and_filters_kept_in_page_links(self):
        response = self.get_history(plate="zzzz")
        self.assertContains(response, "No gate movements match these filters.")
        response = self.get_history(plate="KA02", page=1)
        self.assertEqual(response.context["query_string"], "plate=KA02")

    def test_gate_page_still_works(self):
        response = self.client.get(reverse("tracking:gate"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Record a movement")
