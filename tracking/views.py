from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import GateEntryForm
from .models import VehicleLog
from .utils import todays_counts, vehicles_inside


def gate(request):
    """Record a gate movement (POST) and show the gate summary and recent movements."""
    if request.method == "POST":
        form = GateEntryForm(request.POST)
        if form.is_valid():
            log = form.save()
            movement = log.get_movement_type_display()

            if log.vehicle:
                resident = log.vehicle.resident
                messages.success(
                    request,
                    f"{movement} recorded for {log.plate_number}: "
                    f"registered vehicle of {resident.full_name} ({resident.flat}).",
                )
            elif log.category == VehicleLog.Category.VISITOR:
                messages.success(request, f"{movement} recorded for {log.plate_number}: visitor vehicle.")
            else:
                messages.warning(request, f"{movement} recorded for {log.plate_number}: unknown vehicle.")

            return redirect("tracking:gate")
    else:
        form = GateEntryForm()

    context = {
        "form": form,
        "recent_logs": VehicleLog.objects.select_related("vehicle__resident__flat__wing")[:20],
        "inside_logs": list(vehicles_inside()),
        "today": todays_counts(),
    }
    return render(request, "tracking/gate.html", context)
