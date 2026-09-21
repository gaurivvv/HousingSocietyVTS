from django.core.exceptions import ValidationError
from django.db import models

from residents.models import Resident

from .utils import is_valid_indian_plate, normalize_plate


class Vehicle(models.Model):
    """A vehicle registered to a resident of the society."""

    class VehicleType(models.TextChoices):
        TWO_WHEELER = "TWO_WHEELER", "Two Wheeler"
        FOUR_WHEELER = "FOUR_WHEELER", "Four Wheeler"
        OTHER = "OTHER", "Other"

    resident = models.ForeignKey(
        Resident,
        on_delete=models.PROTECT,
        related_name="vehicles",
    )
    vehicle_number = models.CharField(
        max_length=15,
        unique=True,
        help_text="e.g. MH12AB1234. Spaces and hyphens are removed automatically.",
    )
    vehicle_type = models.CharField(
        max_length=15,
        choices=VehicleType.choices,
        default=VehicleType.FOUR_WHEELER,
    )
    model_name = models.CharField("Model", max_length=50, blank=True)
    colour = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vehicle_number"]

    def __str__(self):
        return self.vehicle_number

    def clean(self):
        # Normalize first, so the uniqueness check compares the cleaned value.
        self.vehicle_number = normalize_plate(self.vehicle_number)

        if self.vehicle_number and not is_valid_indian_plate(self.vehicle_number):
            raise ValidationError({
                "vehicle_number": "Enter a valid Indian vehicle number, e.g. MH12AB1234 or 22BH1234AA."
            })

        self.model_name = (self.model_name or "").strip()
        self.colour = (self.colour or "").strip()

    def save(self, *args, **kwargs):
        # Safety net: normalize even when no form is involved.
        self.vehicle_number = normalize_plate(self.vehicle_number)
        super().save(*args, **kwargs)