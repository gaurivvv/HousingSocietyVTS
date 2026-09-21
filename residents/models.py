from django.core.validators import RegexValidator
from django.db import models

from society.models import Flat

phone_validator = RegexValidator(
    regex=r"^[6-9][0-9]{9}$",
    message="Enter a valid 10-digit Indian mobile number (without +91 or spaces).",
)


class Resident(models.Model):
    """A person living in a flat, either as the owner or as a tenant."""

    class ResidentType(models.TextChoices):
        OWNER = "OWNER", "Owner"
        TENANT = "TENANT", "Tenant"

    flat = models.ForeignKey(
        Flat,
        on_delete=models.PROTECT,
        related_name="residents",
    )
    full_name = models.CharField(max_length=100)
    resident_type = models.CharField(
        max_length=10,
        choices=ResidentType.choices,
        default=ResidentType.OWNER,
    )
    phone = models.CharField(max_length=10, validators=[phone_validator])
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.flat})"

    def _normalize(self):
        # "  Rajesh   Sharma " -> "Rajesh Sharma"
        self.full_name = " ".join((self.full_name or "").split())
        self.email = (self.email or "").strip().lower()

    def clean(self):
        self._normalize()

    def save(self, *args, **kwargs):
        self._normalize()
        super().save(*args, **kwargs)