from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import VisitorForm
from .models import Visitor


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
