from django.db.models import OuterRef, Subquery
from django.utils import timezone

from .models import VehicleLog


def vehicles_inside():
    """
    A vehicle is inside if the most recent log for its plate is an ENTRY.
    Returns that latest ENTRY log for every plate that is currently inside.
    """
    latest_log_for_plate = (
        VehicleLog.objects.filter(plate_number=OuterRef("plate_number"))
        .order_by("-timestamp", "-id")
        .values("id")[:1]
    )
    return (
        VehicleLog.objects.filter(
            id=Subquery(latest_log_for_plate),
            movement_type=VehicleLog.MovementType.ENTRY,
        )
        .select_related("vehicle__resident__flat__wing", "visitor__resident", "visitor__flat__wing")
        .order_by("-timestamp")
    )


def todays_counts():
    """Number of entries and exits recorded today (Indian time)."""
    todays_logs = VehicleLog.objects.filter(timestamp__date=timezone.localdate())
    return {
        "entries": todays_logs.filter(movement_type=VehicleLog.MovementType.ENTRY).count(),
        "exits": todays_logs.filter(movement_type=VehicleLog.MovementType.EXIT).count(),
    }
