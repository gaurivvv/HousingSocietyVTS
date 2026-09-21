from django import forms

from .models import VehicleLog


class GateEntryForm(forms.ModelForm):
    """Form used by the guard at the gate. The time is recorded automatically."""

    class Meta:
        model = VehicleLog
        fields = ["plate_number", "movement_type", "category", "remarks"]
        labels = {
            "plate_number": "Vehicle number",
            "movement_type": "Entry or exit",
            "category": "If the vehicle is not registered",
            "remarks": "Remarks (optional)",
        }
        help_texts = {
            "plate_number": "Type it as seen, e.g. MH 12 AB 1234. Spaces and hyphens are removed automatically.",
            "category": "Registered vehicles are recognised automatically from the plate.",
        }
        widgets = {
            "plate_number": forms.TextInput(attrs={"placeholder": "e.g. MH 12 AB 1234", "autofocus": True}),
            "remarks": forms.Textarea(attrs={"rows": 2, "placeholder": "e.g. delivery van, visiting A-101"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The guard only chooses Unknown or Visitor; Registered is decided by the model.
        self.fields["category"].choices = [
            (VehicleLog.Category.UNKNOWN, "Unknown vehicle"),
            (VehicleLog.Category.VISITOR, "Visitor vehicle"),
        ]

        # Bootstrap styling for every field
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def full_clean(self):
        super().full_clean()
        # Mark fields that have errors, so Bootstrap shows them in red
        for field_name in self.errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                widget.attrs["class"] = widget.attrs.get("class", "") + " is-invalid"
