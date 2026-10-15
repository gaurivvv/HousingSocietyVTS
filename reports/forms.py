"""Date range filter for the reports page.

Follows the same pattern as tracking.forms.HistoryFilterForm: Bootstrap
classes applied in __init__, and cross-field validation in clean().
"""

from datetime import timedelta

from django import forms
from django.utils import timezone

DEFAULT_DAYS = 30
MAX_RANGE_DAYS = 366


class ReportFilterForm(forms.Form):
    """Start and end dates, defaulting to the last 30 days."""

    start_date = forms.DateField(
        label="From date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        label="To date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["start_date"].initial = today - timedelta(days=DEFAULT_DAYS - 1)
        self.fields["end_date"].initial = today
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def full_clean(self):
        super().full_clean()
        for field_name in self.errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                widget.attrs["class"] = widget.attrs.get("class", "") + " is-invalid"

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        if start and end:
            if start > end:
                self.add_error("end_date", "The 'to' date must be on or after the 'from' date.")
            elif (end - start).days > MAX_RANGE_DAYS:
                self.add_error(
                    "end_date",
                    f"Choose a range of {MAX_RANGE_DAYS} days or fewer.",
                )
        return cleaned


def default_range():
    """The range used when the page is opened without filters."""
    today = timezone.localdate()
    return today - timedelta(days=DEFAULT_DAYS - 1), today
