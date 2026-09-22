from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

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
    """The visitor pass: pass code, visit details and the vehicle's gate movements."""
    visitor = get_object_or_404(Visitor.objects.select_related("flat__wing", "resident"), pk=pk)
    # Gate logs linked to this visitor (reverse link from VehicleLog.visitor), in the order they happened
    gate_logs = visitor.gate_logs.order_by("timestamp", "id")
    return render(request, "visitors/visitor_detail.html", {"visitor": visitor, "gate_logs": gate_logs})


# ----- Lifecycle actions: POST only -----

def _redirect_back(request, visitor):
    """Return to the page the button was on, but only if it is on this site."""
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("visitors:visitor_detail", pk=visitor.pk)


def _run_action(request, pk, action_name, success_message):
    visitor = get_object_or_404(Visitor, pk=pk)
    try:
        getattr(visitor, action_name)()
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, success_message.format(name=visitor.full_name, code=visitor.pass_code))
    return _redirect_back(request, visitor)


@require_POST
def visitor_check_in(request, pk):
    return _run_action(request, pk, "check_in", "{name} checked in ({code}).")


@require_POST
def visitor_check_out(request, pk):
    return _run_action(request, pk, "check_out", "{name} checked out ({code}).")


@require_POST
def visitor_cancel(request, pk):
    return _run_action(request, pk, "cancel", "Visit by {name} was cancelled ({code}).")
