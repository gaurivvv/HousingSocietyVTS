from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from vehicles.utils import normalize_plate

from .forms import VisitorFilterForm, VisitorForm
from .models import Visitor


def visitor_list(request):
    """Visitors for one expected date (today by default), with search and status filter."""
    data = request.GET.copy()
    if "date" not in data:
        # No date in the address: show today's visitors
        data["date"] = timezone.localdate().isoformat()
    filter_form = VisitorFilterForm(data)

    visitors = Visitor.objects.select_related("flat__wing", "resident")

    if filter_form.is_valid():
        query = filter_form.cleaned_data["q"].strip()
        if query:
            conditions = (
                Q(full_name__icontains=query)
                | Q(phone__icontains=query)
                | Q(pass_code__icontains=query)
                | Q(resident__full_name__icontains=query)
            )
            normalized = normalize_plate(query)
            if normalized:
                conditions |= Q(vehicle_number__icontains=normalized)
            # Also support "A-101" style searches (wing-flat)
            if "-" in query:
                wing_part, flat_part = query.split("-", 1)
                conditions |= Q(
                    flat__wing__name__iexact=wing_part.strip(),
                    flat__flat_number__iexact=flat_part.strip(),
                )
            visitors = visitors.filter(conditions)

        if filter_form.cleaned_data["date"]:
            visitors = visitors.filter(expected_date=filter_form.cleaned_data["date"])
        if filter_form.cleaned_data["status"]:
            visitors = visitors.filter(status=filter_form.cleaned_data["status"])

    paginator = Paginator(visitors, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Keep the filters (including the date) in the page links
    params = data.copy()
    params.pop("page", None)

    context = {
        "filter_form": filter_form,
        "page_obj": page_obj,
        "total_count": paginator.count,
        "query_string": params.urlencode(),
    }
    return render(request, "visitors/visitor_list.html", context)


def visitor_create(request):
    """Pre-register a visitor, then show their pass."""
    if request.method == "POST":
        form = VisitorForm(request.POST)
        if form.is_valid():
            visitor = form.save()
            messages.success(
                request,
                f"Visitor {visitor.full_name} was pre-registered. Pass code: {visitor.pass_code}",
            )
            return redirect("visitors:visitor_detail", pk=visitor.pk)
    else:
        form = VisitorForm()

    context = {"form": form, "page_title": "Pre-register a Visitor", "submit_label": "Pre-register"}
    return render(request, "visitors/visitor_form.html", context)


def visitor_detail(request, pk):
    """The visitor pass: pass code and visit details."""
    visitor = get_object_or_404(Visitor.objects.select_related("flat__wing", "resident"), pk=pk)
    return render(request, "visitors/visitor_detail.html", {"visitor": visitor})
