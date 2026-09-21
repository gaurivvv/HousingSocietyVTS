from django.db import models


class Wing(models.Model):
    """A building block of the housing society, e.g. Wing A, Wing B."""

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Short wing name or code, e.g. A, B, C.",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def _normalize_name(self):
        # Store names in one format, so "a", " A " and "A" count as the same wing.
        self.name = (self.name or "").strip().upper()

    def clean(self):
        # Runs when data comes from a form (including Django Admin),
        # before Django checks that the name is unique.
        self._normalize_name()

    def save(self, *args, **kwargs):
        # Runs on every save, even when no form is involved.
        self._normalize_name()
        super().save(*args, **kwargs)


class Flat(models.Model):
    """A flat (apartment) inside a wing, e.g. A-101."""

    wing = models.ForeignKey(
        Wing,
        on_delete=models.PROTECT,
        related_name="flats",
    )
    flat_number = models.CharField(
        max_length=10,
        help_text="Flat number within the wing, e.g. 101, 202.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["wing__name", "flat_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["wing", "flat_number"],
                name="unique_flat_number_per_wing",
            ),
        ]

    def __str__(self):
        return f"{self.wing.name}-{self.flat_number}"

    def _normalize_flat_number(self):
        self.flat_number = (self.flat_number or "").strip().upper()

    def clean(self):
        self._normalize_flat_number()

    def save(self, *args, **kwargs):
        self._normalize_flat_number()
        super().save(*args, **kwargs)