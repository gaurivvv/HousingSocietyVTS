from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import ResidentForm
from .models import Resident


def resident_list(request):
    """List residents, with an optional search."""
    query = request.GET.get("q", "").strip()

    residents = Resident.objects.select_related("flat__wing").order_by(
        "flat__wing__name", "flat__flat_number", "full_name"
    )

    if query:
        conditions = (
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(flat__flat_number__icontains=query)
            | Q(flat__wing__name__iexact=query)
        )
        # Also support "A-101" style searches (wing-flat)
        if "-" in query:
            wing_part, flat_part = query.split("-", 1)
            conditions |= Q(
                flat__wing__name__iexact=wing_part.strip(),
                flat__flat_number__iexact=flat_part.strip(),
            )
        residents = residents.filter(conditions)

    context = {"residents": residents, "query": query}
    return render(request, "residents/resident_list.html", context)


def resident_create(request):
    """Show an empty form (GET), or validate and save a new resident (POST)."""
    if request.method == "POST":
        form = ResidentForm(request.POST)
        if form.is_valid():
            resident = form.save()
            messages.success(request, f"Resident {resident.full_name} was added.")
            return redirect("residents:resident_list")
    else:
        form = ResidentForm()

    context = {"form": form, "page_title": "Add Resident", "submit_label": "Add Resident"}
    return render(request, "residents/resident_form.html", context)
