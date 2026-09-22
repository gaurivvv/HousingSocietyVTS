from django.shortcuts import redirect, render

from residents.models import Resident
from society.models import Flat, Wing
from tracking.utils import todays_counts, vehicles_inside
from vehicles.models import Vehicle


def home(request):
    """Home page with live counts from the database.

    Users without any staff permission (for example residents, or accounts with no role yet)
    are sent to their own account page instead.
    """
    user = request.user
    if not (user.has_perm("tracking.view_vehiclelog") or user.has_perm("residents.view_resident")):
        return redirect("accounts:my_account")

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
