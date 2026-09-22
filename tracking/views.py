from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from vehicles.utils import normalize_plate

from .forms import GateEntryForm, HistoryFilterForm
from .models import VehicleLog
from .utils import todays_counts, vehicles_inside


@permission_required(("tracking.add_vehiclelog", "tracking.view_vehiclelog"), raise_exception=True)
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
            elif log.visitor:
                # Matched today's pre-registered visitor (the visitor's status is not changed)
                visitor = log.visitor
                messages.success(
                    request,
                    f"{movement} recorded for {log.plate_number}: "
                    f"visitor {visitor.full_name}, visiting {visitor.resident.full_name} ({visitor.flat}).",
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
        "recent_logs": VehicleLog.objects.select_related(
            "vehicle__resident__flat__wing", "visitor__resident", "visitor__flat__wing"
        )[:20],
        "inside_logs": list(vehicles_inside()),
        "today": todays_counts(),
    }
    return render(request, "tracking/gate.html", context)


@permission_required("tracking.view_vehiclelog", raise_exception=True)
def gate_history(request):
    """All gate movements, newest first, with optional filters and pages of 25."""
    # Bound only when the address has filter values, e.g. /gate/history/?plate=mh12
    filter_form = HistoryFilterForm(request.GET or None)

    logs = VehicleLog.objects.select_related(
        "vehicle__resident__flat__wing", "visitor__resident", "visitor__flat__wing"
    )

    if filter_form.is_valid():
        data = filter_form.cleaned_data

        plate = normalize_plate(data["plate"])
        if plate:
            logs = logs.filter(plate_number__icontains=plate)
        if data["date_from"]:
            logs = logs.filter(timestamp__date__gte=data["date_from"])
        if data["date_to"]:
            logs = logs.filter(timestamp__date__lte=data["date_to"])
        if data["movement_type"]:
            logs = logs.filter(movement_type=data["movement_type"])
        if data["category"]:
            logs = logs.filter(category=data["category"])

    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Keep the filters in the address when moving between pages
    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "filter_form": filter_form,
        "page_obj": page_obj,
        "total_count": paginator.count,
        "query_string": params.urlencode(),
    }
    return render(request, "tracking/history.html", context)
