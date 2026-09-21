from django import forms

from residents.models import Resident

from .models import Vehicle
from .utils import is_valid_indian_plate, normalize_plate


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["resident", "vehicle_number", "vehicle_type", "model_name", "colour"]
        labels = {
            "resident": "Owner (resident)",
            "vehicle_number": "Vehicle number",
            "vehicle_type": "Vehicle type",
            "model_name": "Model (optional)",
            "colour": "Colour (optional)",
        }
        help_texts = {
            "vehicle_number": "e.g. MH12AB1234 or 22BH1234AA. Spaces and hyphens are removed automatically.",
        }
        error_messages = {
            "vehicle_number": {"unique": "This vehicle number is already registered."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active residents can be chosen as owners
        self.fields["resident"].queryset = (
            Resident.objects.filter(is_active=True)
            .select_related("flat__wing")
            .order_by("flat__wing__name", "flat__flat_number", "full_name")
        )
        self.fields["resident"].empty_label = "Select the owner"

        # Bootstrap styling for every field
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_vehicle_number(self):
        # Normalize first, so the format and uniqueness checks use the stored format
        number = normalize_plate(self.cleaned_data["vehicle_number"])
        if not is_valid_indian_plate(number):
            raise forms.ValidationError(
                "Enter a valid Indian vehicle number, e.g. MH12AB1234 or 22BH1234AA."
            )
        return number

    def full_clean(self):
        super().full_clean()
        # Mark fields that have errors, so Bootstrap shows them in red
        for field_name in self.errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                widget.attrs["class"] = widget.attrs.get("class", "") + " is-invalid"
