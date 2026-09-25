from django.shortcuts import redirect, render
from django.utils import timezone

from residents.models import Resident
from society.models import Flat, Wing
from tracking.models import VehicleLog
from tracking.utils import todays_counts, vehicles_inside
from vehicles.models import Vehicle
from visitors.models import Visitor


def home(request):
    """Home page with live counts and recent activity from the database.

    Users without any staff permission (for example residents, or accounts with no role yet)
    are sent to their own account page instead.

    Recent activity is only built for users who may view it: gate movements need
    tracking.view_vehiclelog and visitors need visitors.view_visitor.
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
        "recent_logs": None,
        "recent_visitors": None,
        "todays_visitor_count": None,
    }

    if user.has_perm("tracking.view_vehiclelog"):
        context["recent_logs"] = VehicleLog.objects.select_related(
            "vehicle__resident__flat__wing", "visitor__resident", "visitor__flat__wing"
        )[:8]

    if user.has_perm("visitors.view_visitor"):
        visitors = Visitor.objects.select_related("flat__wing", "resident")
        context["recent_visitors"] = visitors[:8]
        context["todays_visitor_count"] = Visitor.objects.filter(
            expected_date=timezone.localdate()
        ).count()

    return render(request, "dashboard/home.html", context)
