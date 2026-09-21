import re

from django import forms

from society.models import Flat

from .models import Resident


class ResidentForm(forms.ModelForm):
    # Declared here (instead of taken from the model) so users can type
    # "+91 98765 43210". clean_phone() reduces it to 10 digits, and then the
    # model's phone validator checks the final value.
    phone = forms.CharField(
        label="Mobile number",
        max_length=15,
        help_text="10-digit mobile number. Spaces and +91 are removed automatically.",
    )

    class Meta:
        model = Resident
        fields = ["flat", "full_name", "resident_type", "phone", "email"]
        labels = {
            "flat": "Flat",
            "full_name": "Full name",
            "resident_type": "Owner / Tenant",
            "email": "Email (optional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["flat"].queryset = Flat.objects.select_related("wing").order_by(
            "wing__name", "flat_number"
        )
        self.fields["flat"].empty_label = "Select a flat"

        # Bootstrap styling for every field
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_full_name(self):
        full_name = " ".join(self.cleaned_data["full_name"].split())
        if any(char.isdigit() for char in full_name):
            raise forms.ValidationError("Name should not contain numbers.")
        return full_name

    def clean_phone(self):
        phone = re.sub(r"[\s-]", "", self.cleaned_data["phone"])
        if phone.startswith("+91"):
            phone = phone[3:]
        elif phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]
        return phone

    def clean(self):
        cleaned_data = super().clean()
        flat = cleaned_data.get("flat")
        full_name = cleaned_data.get("full_name")

        # The same person should not be recorded twice for the same flat
        if flat and full_name:
            duplicates = Resident.objects.filter(flat=flat, full_name__iexact=full_name)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error(
                    "full_name",
                    f"{full_name} is already recorded for flat {flat}. Edit that record instead.",
                )
        return cleaned_data

    def full_clean(self):
        super().full_clean()
        # Mark fields that have errors, so Bootstrap shows them in red
        for field_name in self.errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                widget.attrs["class"] = widget.attrs.get("class", "") + " is-invalid"
