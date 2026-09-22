from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from vehicles.models import Vehicle
from vehicles.utils import normalize_plate
from visitors.models import Visitor  # NEW


class VehicleLog(models.Model):
    """One vehicle movement (entry or exit) at the society gate."""

    class MovementType(models.TextChoices):
        ENTRY = "ENTRY", "Entry"
        EXIT = "EXIT", "Exit"

    class Category(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        VISITOR = "VISITOR", "Visitor"
        UNKNOWN = "UNKNOWN", "Unknown"

    # Optional link: unknown and visitor vehicles have no Vehicle record.
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="logs",
        help_text="Linked automatically when the plate matches a registered vehicle.",
    )
    # NEW: optional link to a pre-registered visitor whose vehicle this is.
    visitor = models.ForeignKey(
        Visitor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gate_logs",
        help_text="Linked automatically when the plate matches an expected or checked-in visitor for that day.",
    )
    plate_number = models.CharField(
        max_length=15,
        help_text="As seen at the gate. Spaces and hyphens are removed automatically.",
    )
    movement_type = models.CharField(max_length=5, choices=MovementType.choices)
    category = models.CharField(
        max_length=10,
        choices=Category.choices,
        default=Category.UNKNOWN,
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["plate_number"])]

    def __str__(self):
        local_time = timezone.localtime(self.timestamp)
        return f"{self.plate_number} {self.get_movement_type_display()} at {local_time:%d-%m-%Y %H:%M}"

    def _matching_visitor(self):
        """NEW: today's (the log's own date, Indian time) Expected or Checked-in visitor with this plate.
        A Checked-in visitor is preferred; then the earliest registered."""
        visit_date = timezone.localdate(self.timestamp)
        candidates = Visitor.objects.filter(vehicle_number=self.plate_number, expected_date=visit_date)
        return (
            candidates.filter(status=Visitor.Status.CHECKED_IN).order_by("created_at").first()
            or candidates.filter(status=Visitor.Status.EXPECTED).order_by("created_at").first()
        )

    def _apply_rules(self):
        """Normalize the plate, link a registered vehicle or a visitor if one matches, and set the category."""
        self.plate_number = normalize_plate(self.plate_number)

        # A registered vehicle was chosen but no plate typed: use the vehicle's plate
        if self.vehicle_id and not self.plate_number:
            self.plate_number = self.vehicle.vehicle_number

        # No vehicle chosen: link one automatically if the plate is registered
        if not self.vehicle_id and self.plate_number:
            self.vehicle = Vehicle.objects.filter(vehicle_number=self.plate_number).first()

        # Priority 1: a registered resident vehicle is always REGISTERED, never a visitor
        if self.vehicle_id:
            self.category = self.Category.REGISTERED
            self.visitor = None  # NEW
            return

        # NEW - Priority 2: a matching visitor for that day makes it a VISITOR
        if not self.visitor_id and self.plate_number:
            self.visitor = self._matching_visitor()
        if self.visitor_id:
            self.category = self.Category.VISITOR
            return

        # Priority 3: REGISTERED cannot be claimed for a plate that is not registered.
        # UNKNOWN stays UNKNOWN; a VISITOR chosen by the guard is kept.
        if self.category == self.Category.REGISTERED:
            self.category = self.Category.UNKNOWN

    def clean(self):
        self._apply_rules()
        if self.plate_number and len(self.plate_number) < 4:
            raise ValidationError({"plate_number": "Enter the full vehicle number seen at the gate."})
        if self.vehicle_id and self.plate_number != self.vehicle.vehicle_number:
            raise ValidationError({"plate_number": "Plate number does not match the selected vehicle."})
        # NEW: same consistency rule for a linked visitor
        if self.visitor_id and self.plate_number != self.visitor.vehicle_number:
            raise ValidationError({"plate_number": "Plate number does not match the linked visitor's vehicle."})

    def save(self, *args, **kwargs):
        # Apply the same rules even when saving without a form (e.g. a future API)
        self._apply_rules()
        super().save(*args, **kwargs)
