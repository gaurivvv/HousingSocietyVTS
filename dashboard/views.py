from django.shortcuts import render

from residents.models import Resident
from society.models import Flat, Wing
from tracking.utils import todays_counts, vehicles_inside
from vehicles.models import Vehicle


def home(request):
    """Home page with live counts from the database."""
    today = todays_counts()
    context = {
        "wing_count": Wing.objects.count(),
        "flat_count": Flat.objects.count(),
        "active_resident_count": Resident.objects.filter(is_active=True).count(),
        "active_vehicle_count": Vehicle.objects.filter(is_active=True).count(),
        "inside_count": vehicles_inside().count(),
        "todays_entries": today["entries"],
        "todays_exits": today["exits"],
    }
    return render(request, "dashboard/home.html", context)
