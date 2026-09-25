"""Create a small, realistic demo dataset for a live demonstration.

Safe to run repeatedly: every record is matched on a natural key first, so nothing
is duplicated. All records go through the normal model validation and the real
visitor lifecycle methods; no business rule is bypassed and no status is forced.

Gate movements are created for today, so the dashboard figures are meaningful.
Running the command on a later day adds that day's movements as well.
"""

import datetime

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.roles import GUARD, RESIDENT
from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from vehicles.models import Vehicle
from visitors.models import Visitor

FLATS = [("A", "102"), ("A", "201"), ("A", "202"), ("B", "101"), ("B", "102"), ("B", "201")]

RESIDENTS = [
    ("Rajesh Sharma", "A", "102", "OWNER", "9876543210", "rajesh.sharma@example.com"),
    ("Priya Patil", "A", "201", "OWNER", "9823456781", "priya.patil@example.com"),
    ("Amit Kulkarni", "A", "202", "TENANT", "9834567812", "amit.kulkarni@example.com"),
    ("Sneha Joshi", "B", "101", "OWNER", "9845678123", "sneha.joshi@example.com"),
    ("Vikram Rao", "B", "102", "TENANT", "9856781234", ""),
    ("Meera Nair", "B", "201", "OWNER", "9867812345", "meera.nair@example.com"),
]

VEHICLES = [
    ("MH12KL4567", "Rajesh Sharma", "FOUR_WHEELER", "Hyundai i20", "White"),
    ("MH14PQ2345", "Priya Patil", "TWO_WHEELER", "Honda Activa", "Grey"),
    ("MH12RS6789", "Amit Kulkarni", "FOUR_WHEELER", "Maruti Baleno", "Silver"),
    ("MH14TU1122", "Sneha Joshi", "TWO_WHEELER", "TVS Jupiter", "Blue"),
    ("MH12VW3344", "Vikram Rao", "FOUR_WHEELER", "Tata Nexon", "Red"),
    ("MH14XY5566", "Meera Nair", "TWO_WHEELER", "Bajaj Pulsar", "Black"),
]

# (name, phone, host, vehicle, days_ago, action)
VISITORS = [
    ("Rohit Deshmukh", "9811223344", "Rajesh Sharma", "MH14GH7788", 0, None),
    ("Sneha Kulkarni", "9822334455", "Priya Patil", "", 0, "check_in"),
    ("Anil Pawar", "9833445566", "Amit Kulkarni", "MH14JK9900", 0, "check_out"),
    ("Manoj Shinde", "9844556677", "Sneha Joshi", "", 1, None),
]

# (plate, movement, hour, minute, days_ago, remarks)
MOVEMENTS = [
    ("MH12KL4567", "ENTRY", 8, 15, 0, ""),
    ("MH14PQ2345", "ENTRY", 8, 40, 0, ""),
    ("MH12KL4567", "EXIT", 9, 30, 0, ""),
    ("MH14GH7788", "ENTRY", 10, 5, 0, "Visitor for A-102"),
    ("MH12RS6789", "ENTRY", 10, 50, 0, ""),
    ("MH14TU1122", "ENTRY", 11, 20, 0, ""),
    ("KA05ZZ9911", "ENTRY", 12, 0, 0, "Courier van, gate pass issued"),
    ("MH14PQ2345", "EXIT", 13, 15, 0, ""),
    ("MH12VW3344", "ENTRY", 18, 40, 1, ""),
    ("MH12VW3344", "EXIT", 19, 55, 1, ""),
]


class Command(BaseCommand):
    help = "Create a small, realistic demo dataset. Safe to run more than once."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Create demo_resident and demo_guard logins with this password. "
                 "Without it, no login is created.",
        )

    def handle(self, *args, **options):
        created = {"wings": 0, "flats": 0, "residents": 0, "vehicles": 0,
                   "visitors": 0, "movements": 0, "logins": 0}

        with transaction.atomic():
            self._society(created)
            people = self._residents(created)
            self._vehicles(created, people)
            self._visitors(created, people)
            self._movements(created)
            self._logins(created, people, options.get("password"))

        for name, count in created.items():
            word = "added" if count else "already present"
            self.stdout.write(f"{name:<10} {count} {word}")

        if not options.get("password"):
            self.stdout.write(self.style.WARNING(
                "No demo logins created. Re-run with --password to add demo_resident and demo_guard."
            ))
        self.stdout.write(self.style.SUCCESS("Demo data is ready."))

    def _society(self, created):
        for wing_name, flat_number in FLATS:
            wing, made = Wing.objects.get_or_create(name=wing_name)
            created["wings"] += int(made)
            _, made = Flat.objects.get_or_create(wing=wing, flat_number=flat_number)
            created["flats"] += int(made)

    def _residents(self, created):
        people = {}
        for name, wing_name, flat_number, kind, phone, email in RESIDENTS:
            flat = Flat.objects.get(wing__name=wing_name, flat_number=flat_number)
            resident = Resident.objects.filter(flat=flat, full_name=name).first()
            if resident is None:
                resident = Resident(flat=flat, full_name=name, resident_type=kind,
                                    phone=phone, email=email, is_active=True)
                resident.full_clean()
                resident.save()
                created["residents"] += 1
            people[name] = resident
        return people

    def _vehicles(self, created, people):
        for plate, owner, kind, model, colour in VEHICLES:
            if Vehicle.objects.filter(vehicle_number=plate).exists():
                continue
            vehicle = Vehicle(resident=people[owner], vehicle_number=plate,
                              vehicle_type=kind, model_name=model, colour=colour)
            vehicle.full_clean()
            vehicle.save()
            created["vehicles"] += 1

    def _visitors(self, created, people):
        today = timezone.localdate()
        for name, phone, host_name, plate, days_ago, action in VISITORS:
            host = people[host_name]
            expected = today - datetime.timedelta(days=days_ago)
            if Visitor.objects.filter(full_name=name, resident=host, expected_date=expected).exists():
                continue
            visitor = Visitor(full_name=name, phone=phone, flat=host.flat, resident=host,
                              vehicle_number=plate, expected_date=expected)
            visitor.full_clean()
            visitor.save()
            created["visitors"] += 1
            # Statuses are reached through the real lifecycle methods, never set directly
            if action == "check_in":
                visitor.check_in()
            elif action == "check_out":
                visitor.check_in()
                visitor.check_out()

    def _movements(self, created):
        today = timezone.localdate()
        for plate, movement, hour, minute, days_ago, remarks in MOVEMENTS:
            moment = timezone.make_aware(datetime.datetime.combine(
                today - datetime.timedelta(days=days_ago), datetime.time(hour, minute)
            ))
            if VehicleLog.objects.filter(plate_number=plate, movement_type=movement,
                                         timestamp=moment).exists():
                continue
            # The model decides the category and links the vehicle or visitor itself
            log = VehicleLog(plate_number=plate, movement_type=movement,
                             category=VehicleLog.Category.UNKNOWN,
                             timestamp=moment, remarks=remarks)
            log.full_clean()
            log.save()
            created["movements"] += 1

    def _logins(self, created, people, password):
        if not password:
            return
        resident_group = Group.objects.filter(name=RESIDENT).first()
        guard_group = Group.objects.filter(name=GUARD).first()
        if resident_group is None or guard_group is None:
            self.stdout.write(self.style.WARNING(
                "Role groups are missing. Run: python manage.py setup_roles"
            ))
            return

        login, made = User.objects.get_or_create(
            username="demo_resident", defaults={"first_name": "Rajesh", "last_name": "Sharma"}
        )
        if made:
            login.set_password(password)
            login.save()
            login.groups.add(resident_group)
            created["logins"] += 1
        rajesh = people["Rajesh Sharma"]
        if rajesh.user_id is None and not Resident.objects.filter(user=login).exists():
            rajesh.user = login
            rajesh.save()

        guard, made = User.objects.get_or_create(
            username="demo_guard", defaults={"first_name": "Suresh", "last_name": "Yadav"}
        )
        if made:
            guard.set_password(password)
            guard.save()
            guard.groups.add(guard_group)
            created["logins"] += 1
