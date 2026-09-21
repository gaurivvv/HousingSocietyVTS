from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import VehicleForm
from .models import Vehicle
from .utils import normalize_plate


def vehicle_list(request):
    """List vehicles, with an optional search and vehicle type filter."""
    query = request.GET.get("q", "").strip()
    vehicle_type = request.GET.get("type", "")

    vehicles = Vehicle.objects.select_related("resident__flat__wing").order_by("vehicle_number")

    # Only accept one of the model's real choices; ignore anything else
    if vehicle_type in Vehicle.VehicleType.values:
        vehicles = vehicles.filter(vehicle_type=vehicle_type)

    if query:
        conditions = (
            Q(model_name__icontains=query)
            | Q(colour__icontains=query)
            | Q(resident__full_name__icontains=query)
            | Q(resident__phone__icontains=query)
        )
        # Match plates however they are typed: "mh 12-ab" -> "MH12AB"
        normalized = normalize_plate(query)
        if normalized:
            conditions |= Q(vehicle_number__icontains=normalized)
        # Also support "A-101" style searches (owner's wing-flat)
        if "-" in query:
            wing_part, flat_part = query.split("-", 1)
            conditions |= Q(
                resident__flat__wing__name__iexact=wing_part.strip(),
                resident__flat__flat_number__iexact=flat_part.strip(),
            )
        vehicles = vehicles.filter(conditions)

    context = {
        "vehicles": vehicles,
        "query": query,
        "vehicle_type": vehicle_type,
        "vehicle_types": Vehicle.VehicleType.choices,
    }
    return render(request, "vehicles/vehicle_list.html", context)


def vehicle_create(request):
    """Show an empty form (GET), or validate and register a new vehicle (POST)."""
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save()
            messages.success(
                request,
                f"Vehicle {vehicle.vehicle_number} was registered to {vehicle.resident.full_name}.",
            )
            return redirect("vehicles:vehicle_list")
    else:
        form = VehicleForm()

    context = {"form": form, "page_title": "Add Vehicle", "submit_label": "Register Vehicle"}
    return render(request, "vehicles/vehicle_form.html", context)


def vehicle_update(request, pk):
    """Show the form filled with a vehicle's details (GET), or save changes (POST)."""
    vehicle = get_object_or_404(Vehicle, pk=pk)

    if request.method == "POST":
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, f"Vehicle {vehicle.vehicle_number} was updated.")
            return redirect("vehicles:vehicle_list")
    else:
        form = VehicleForm(instance=vehicle)

    context = {
        "form": form,
        "vehicle": vehicle,
        "page_title": "Edit Vehicle",
        "submit_label": "Save Changes",
    }
    return render(request, "vehicles/vehicle_form.html", context)
