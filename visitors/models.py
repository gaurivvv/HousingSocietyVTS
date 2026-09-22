import secrets

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from residents.models import Resident, phone_validator
from society.models import Flat
from vehicles.utils import normalize_plate

# Letters and digits that are easy to read aloud (no 0/O or 1/I)
PASS_CODE_CHARACTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_pass_code():
    """A random, hard-to-guess code such as VP-7K3QMX."""
    return "VP-" + "".join(secrets.choice(PASS_CODE_CHARACTERS) for _ in range(6))


class Visitor(models.Model):
    """A person visiting a resident of the society."""

    class Status(models.TextChoices):
        EXPECTED = "EXPECTED", "Expected"
        CHECKED_IN = "CHECKED_IN", "Checked in"
        CHECKED_OUT = "CHECKED_OUT", "Checked out"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=10, validators=[phone_validator])

    flat = models.ForeignKey(Flat, on_delete=models.PROTECT, related_name="visitors")
    resident = models.ForeignKey(Resident, on_delete=models.PROTECT, related_name="visitors")

    vehicle_number = models.CharField(
        max_length=15,
        blank=True,
        help_text="Optional. Spaces and hyphens are removed automatically.",
    )

    expected_date = models.DateField(default=timezone.localdate)
    entry_time = models.DateTimeField(null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EXPECTED)
    pass_code = models.CharField(max_length=9, unique=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expected_date", "-created_at"]
        indexes = [
            models.Index(fields=["vehicle_number"]),
            models.Index(fields=["expected_date"]),
        ]

    def __str__(self):
        return f"{self.full_name} visiting {self.flat} ({self.pass_code})"

    def _normalize(self):
        self.full_name = " ".join((self.full_name or "").split())
        self.vehicle_number = normalize_plate(self.vehicle_number)

    def clean(self):
        self._normalize()
        errors = {}

        if self.vehicle_number and len(self.vehicle_number) < 4:
            errors["vehicle_number"] = "Enter the full vehicle number, or leave it empty."

        # The resident being visited must live in the flat being visited
        if self.flat_id and self.resident_id and self.resident.flat_id != self.flat_id:
            errors["resident"] = "This resident does not live in the selected flat."
        elif not self.pk and self.resident_id and not self.resident.is_active:
            errors["resident"] = "This resident is inactive."

        # Entry and exit times must make sense
        if self.exit_time and not self.entry_time:
            errors["exit_time"] = "A visitor cannot exit before entering."
        elif self.exit_time and self.entry_time and self.exit_time < self.entry_time:
            errors["exit_time"] = "Exit time must be after entry time."

        # The status must match the entry and exit times
        not_arrived = [self.Status.EXPECTED, self.Status.CANCELLED, self.Status.EXPIRED]
        if self.status in not_arrived and (self.entry_time or self.exit_time):
            errors["status"] = f"A visitor who is {self.get_status_display().lower()} cannot have entry or exit times."
        elif self.status == self.Status.CHECKED_IN and (not self.entry_time or self.exit_time):
            errors["status"] = "A checked-in visitor needs an entry time and no exit time."
        elif self.status == self.Status.CHECKED_OUT and not (self.entry_time and self.exit_time):
            errors["status"] = "A checked-out visitor needs both an entry time and an exit time."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._normalize()
        if not self.pass_code:
            code = generate_pass_code()
            while Visitor.objects.filter(pass_code=code).exists():
                code = generate_pass_code()
            self.pass_code = code
        super().save(*args, **kwargs)

    # ----- Lifecycle actions (used by the visitor pages now, and by the API later) -----

    @property
    def can_check_in(self):
        """Only an expected visitor, and only on their expected date."""
        return self.status == self.Status.EXPECTED and self.expected_date == timezone.localdate()

    @property
    def can_check_out(self):
        return self.status == self.Status.CHECKED_IN

    @property
    def can_cancel(self):
        return self.status == self.Status.EXPECTED

    def check_in(self):
        """EXPECTED -> CHECKED_IN, recording the entry time."""
        if self.status != self.Status.EXPECTED:
            raise ValidationError(
                f"Only an expected visitor can be checked in (this visitor is {self.get_status_display().lower()})."
            )
        if self.expected_date != timezone.localdate():
            raise ValidationError("A visitor can only be checked in on their expected date.")
        self.status = self.Status.CHECKED_IN
        self.entry_time = timezone.now()
        self.full_clean()
        self.save()

    def check_out(self):
        """CHECKED_IN -> CHECKED_OUT, recording the exit time."""
        if self.status != self.Status.CHECKED_IN:
            raise ValidationError("Only a checked-in visitor can be checked out.")
        self.status = self.Status.CHECKED_OUT
        self.exit_time = timezone.now()
        self.full_clean()
        self.save()

    def cancel(self):
        """EXPECTED -> CANCELLED (the visitor never arrived)."""
        if self.status != self.Status.EXPECTED:
            raise ValidationError("Only an expected visitor can be cancelled.")
        self.status = self.Status.CANCELLED
        self.full_clean()
        self.save()
