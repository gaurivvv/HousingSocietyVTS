"""Society-wide reports.

Restricted to Society Admin. Guards work the gate and see individual
movements; aggregate analytics across months are a management function.
residents.view_resident is the permission the project already uses to mark
admin-only data, so the same marker is used here.

Every figure comes from database aggregation in reports.utils. The view does
no counting of its own.
"""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from .forms import ReportFilterForm, default_range
from .utils import (
    add_bar_widths,
    gate_by_day,
    gate_totals,
    visitor_totals,
    visitors_by_day,
)


@permission_required("residents.view_resident", raise_exception=True)
def reports(request):
    """Gate and visitor statistics for a date range, defaulting to 30 days."""
    start_date, end_date = default_range()
    filters_applied = False

    # Bound only when the address carries dates, e.g. /reports/?start_date=...
    form = ReportFilterForm(request.GET or None)

    if request.GET:
        if form.is_valid():
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]
            filters_applied = True
        else:
            # Invalid dates: show the errors and report on the default range
            # rather than an arbitrary one the user did not ask for.
            start_date, end_date = default_range()

    gate_rows = add_bar_widths(gate_by_day(start_date, end_date), "total")
    visitor_rows = add_bar_widths(visitors_by_day(start_date, end_date), "registered")

    gate = gate_totals(start_date, end_date)
    visitors = visitor_totals(start_date, end_date)

    context = {
        "form": form,
        "start_date": start_date,
        "end_date": end_date,
        "day_count": (end_date - start_date).days + 1,
        "filters_applied": filters_applied,
        "gate": gate,
        "visitors": visitors,
        "gate_rows": gate_rows,
        "visitor_rows": visitor_rows,
        "has_any_data": bool(gate_rows or visitor_rows),
    }
    return render(request, "reports/reports.html", context)
