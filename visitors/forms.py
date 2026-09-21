import re

from django import forms
from django.utils import timezone

from residents.models import Resident

from .models import Visitor


def clean_indian_mobile(value):
    """Tidy a typed phone number, e.g. '+91 98765 43210' -> '9876543210'.
    The model's phone validator then checks the final value."""
    phone = re.sub(r"[\s-]", "", value)
    if phone.startswith("+91"):
        phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    return phone


def apply_bootstrap(form):
    """Give every field in a form the right Bootstrap class."""
    for field in form.fields.values():
        if isinstance(field.widget, forms.Select):
            field.widget.attrs["class"] = "form-select"
        else:
            field.widget.attrs["class"] = "form-control"


class VisitorForm(forms.ModelForm):
    phone = forms.CharField(
        label="Mobile number",
        max_length=15,
        help_text="10-digit mobile number. Spaces and +91 are removed automatically.",
    )

    class Meta:
        model = Visitor
        fields = ["full_name", "phone", "resident", "vehicle_number", "expected_date"]
        labels = {
            "full_name": "Visitor name",
            "resident": "Visiting (resident and flat)",
            "vehicle_number": "Vehicle number (optional)",
            "expected_date": "Expected date",
        }
        help_texts = {
            "vehicle_number": "Leave empty if the visitor is coming on foot. Spaces and hyphens are removed automatically.",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "e.g. Amit Kulkarni"}),
            "vehicle_number": forms.TextInput(attrs={"placeholder": "e.g. MH 14 CD 5678"}),
            "expected_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active residents can receive new visitors; each is shown as "Name (A-101)"
        self.fields["resident"].queryset = (
            Resident.objects.filter(is_active=True)
            .select_related("flat__wing")
            .order_by("flat__wing__name", "flat__flat_number", "full_name")
        )
        self.fields["resident"].empty_label = "Select the resident being visited"
        apply_bootstrap(self)

    def clean_full_name(self):
        full_name = " ".join(self.cleaned_data["full_name"].split())
        if any(char.isdigit() for char in full_name):
            raise forms.ValidationError("Name should not contain numbers.")
        return full_name

    def clean_phone(self):
        return clean_indian_mobile(self.cleaned_data["phone"])

    def clean_expected_date(self):
        expected_date = self.cleaned_data["expected_date"]
        if expected_date < timezone.localdate():
            raise forms.ValidationError("The expected date cannot be in the past.")
        return expected_date

    def clean(self):
        cleaned_data = super().clean()
        resident = cleaned_data.get("resident")
        if resident:
            # The flat being visited is always the chosen resident's flat
            self.instance.flat = resident.flat
        return cleaned_data

    def full_clean(self):
        super().full_clean()
        # Mark fields that have errors, so Bootstrap shows them in red
        for field_name in self.errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                widget.attrs["class"] = widget.attrs.get("class", "") + " is-invalid"


class VisitorFilterForm(forms.Form):
    """Filters for the Visitors list. Every field is optional."""

    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"placeholder": "Name, phone, pass code, vehicle or flat (A-101)"}),
    )
    date = forms.DateField(
        required=False,
        label="Expected date",
        help_text="Clear the date to see all dates.",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    status = forms.ChoiceField(
        required=False,
        label="Status",
        choices=[("", "All")] + list(Visitor.Status.choices),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)
