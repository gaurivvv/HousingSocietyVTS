from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from vehicles.models import Vehicle
from vehicles.utils import normalize_plate
from visitors.models import Visitor

from .anpr_service import run_anpr
from .forms import GateEntryForm, HistoryFilterForm
from .models import VehicleLog
from .utils import todays_counts, vehicles_inside


@permission_required(("tracking.add_vehiclelog", "tracking.view_vehiclelog"), raise_exception=True)
def gate(request):
    """Record a gate movement (POST) and show the gate summary and recent movements."""
    if request.method == "POST":
        form = GateEntryForm(request.POST)
        if form.is_valid():
            # The user is taken from the session, never from the posted data.
            # GateEntryForm has no field for it, so a crafted POST cannot set it.
            log = form.save(commit=False)
            log.recorded_by = request.user
            log.save()
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
        prefill_plate = request.GET.get("prefill", "").strip()
        if prefill_plate:
            form = GateEntryForm(initial={
                "plate_number": prefill_plate,
                "remarks": "AI-assisted (Verified by Guard)",
            })
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


@permission_required("tracking.add_vehiclelog", raise_exception=True)
def gate_anpr_scan(request):
    """Analyze an uploaded vehicle image using the ANPR pipeline.

    Returns candidate detection results for guard verification.
    This view NEVER records a movement directly to the database.
    """
    if request.method != "POST" or "image" not in request.FILES:
        return JsonResponse({"success": False, "error": "An image file is required."}, status=400)

    uploaded_image = request.FILES["image"]
    anpr_result = run_anpr(uploaded_image)

    if not anpr_result.get("success"):
        return JsonResponse({
            "success": False,
            "error": anpr_result.get("error", "No plate or vehicle recognized in image."),
        }, status=400)

    candidate_plate = (anpr_result.get("candidate_plate") or "").strip()
    match_type = "unknown"
    owner_info = None

    if candidate_plate:
        normalized = normalize_plate(candidate_plate)
        # Check registered resident vehicle
        vehicle = (
            Vehicle.objects
            .select_related("resident__flat__wing")
            .filter(vehicle_number=normalized)
            .first()
        )
        if vehicle:
            match_type = "registered"
            owner_info = f"{vehicle.resident.full_name} ({vehicle.resident.flat})"
        else:
            # Check expected visitor today
            today = timezone.localdate()
            visitor = (
                Visitor.objects
                .select_related("resident__flat__wing")
                .filter(vehicle_number=normalized, expected_date=today)
                .first()
            )
            if visitor:
                match_type = "visitor"
                owner_info = f"Visitor: {visitor.full_name} visiting {visitor.resident.full_name} ({visitor.flat})"

    return JsonResponse({
        "success": True,
        "candidate_plate": candidate_plate,
        "raw_text": anpr_result.get("raw_text", ""),
        "vehicle_detected": anpr_result.get("vehicle_detected", False),
        "vehicle_type": anpr_result.get("vehicle_type"),
        "vehicle_confidence": anpr_result.get("vehicle_confidence"),
        "plate_detected": anpr_result.get("plate_detected", False),
        "plate_confidence": anpr_result.get("plate_confidence"),
        "ocr_confidence": anpr_result.get("ocr_confidence"),
        "match_type": match_type,
        "owner_info": owner_info,
        "corrections": anpr_result.get("corrections", []),
        "uncertain": anpr_result.get("uncertain", False),
        "notice": (
            "ANPR reading is an AI recommendation. The guard must verify "
            "the physical plate with the driver before recording."
        ),
    })


@permission_required("tracking.view_vehiclelog", raise_exception=True)
def gate_history(request):
    """All gate movements, newest first, with optional filters and pages of 25."""
    # Bound only when the address has filter values, e.g. /gate/history/?plate=mh12
    filter_form = HistoryFilterForm(request.GET or None)

    # recorded_by is joined here so the table does not fire one extra query
    # per row for the username.
    logs = VehicleLog.objects.select_related(
        "vehicle__resident__flat__wing", "visitor__resident", "visitor__flat__wing",
        "recorded_by",
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
