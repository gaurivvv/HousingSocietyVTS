from django import forms

from .models import VehicleLog


class BootstrapFormMixin:
    """Adds Bootstrap classes to every field and marks fields with errors in red."""

    def apply_bootstrap(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def full_clean(self):
        super().full_clean()
        for field_name in self.errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                widget.attrs["class"] = widget.attrs.get("class", "") + " is-invalid"


class GateEntryForm(BootstrapFormMixin, forms.ModelForm):
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
        self.apply_bootstrap()


class HistoryFilterForm(BootstrapFormMixin, forms.Form):
    """Filters for the Gate History page. Every field is optional."""

    plate = forms.CharField(
        required=False,
        label="Vehicle number",
        widget=forms.TextInput(attrs={"placeholder": "e.g. MH 12 AB"}),
    )
    date_from = forms.DateField(
        required=False,
        label="From date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        label="To date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    movement_type = forms.ChoiceField(
        required=False,
        label="Movement",
        choices=[("", "All")] + list(VehicleLog.MovementType.choices),
    )
    category = forms.ChoiceField(
        required=False,
        label="Category",
        choices=[("", "All")] + list(VehicleLog.Category.choices),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "The 'to' date must be on or after the 'from' date.")
        return cleaned_data
