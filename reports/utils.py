"""Aggregation for the reports page.

Every figure here is produced by the database, not by looping over rows in
Python. The number of queries does not grow with the size of the date range.

A note on visitor counts, because the two are easy to confuse:

    registered - a Visitor row exists for that date. Someone was expected.
    arrived    - entry_time is set. Someone actually came through the gate.

A visit can be registered and never arrive: cancelled, expired, or simply not
turned up. Reporting only the row count would overstate how many people
actually visited.
"""

from django.db.models import Count, Q
from django.db.models.functions import TruncDate

from tracking.models import VehicleLog
from visitors.models import Visitor


def gate_totals(start_date, end_date):
    """Entry, exit and classification totals for the range."""
    logs = VehicleLog.objects.filter(timestamp__date__range=(start_date, end_date))
    return logs.aggregate(
        entries=Count("id", filter=Q(movement_type=VehicleLog.MovementType.ENTRY)),
        exits=Count("id", filter=Q(movement_type=VehicleLog.MovementType.EXIT)),
        registered=Count("id", filter=Q(category=VehicleLog.Category.REGISTERED)),
        visitor_vehicles=Count("id", filter=Q(category=VehicleLog.Category.VISITOR)),
        unknown=Count("id", filter=Q(category=VehicleLog.Category.UNKNOWN)),
        total=Count("id"),
    )


def gate_by_day(start_date, end_date):
    """One row per day with movements, newest first.

    Days with no movements do not appear: the database has nothing to group.
    """
    return list(
        VehicleLog.objects
        .filter(timestamp__date__range=(start_date, end_date))
        .annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(
            entries=Count("id", filter=Q(movement_type=VehicleLog.MovementType.ENTRY)),
            exits=Count("id", filter=Q(movement_type=VehicleLog.MovementType.EXIT)),
            total=Count("id"),
        )
        .order_by("-day")
    )


def visitor_totals(start_date, end_date):
    """Visitor figures for the range, by expected date.

    'registered' counts visits that were booked. 'arrived' counts those where
    someone was actually checked in. The two differ whenever a visit was
    cancelled, expired, or simply did not happen.
    """
    visitors = Visitor.objects.filter(expected_date__range=(start_date, end_date))
    return visitors.aggregate(
        registered=Count("id"),
        arrived=Count("id", filter=Q(entry_time__isnull=False)),
        checked_out=Count("id", filter=Q(status=Visitor.Status.CHECKED_OUT)),
        still_inside=Count("id", filter=Q(status=Visitor.Status.CHECKED_IN)),
        cancelled=Count("id", filter=Q(status=Visitor.Status.CANCELLED)),
        expired=Count("id", filter=Q(status=Visitor.Status.EXPIRED)),
        expected=Count("id", filter=Q(status=Visitor.Status.EXPECTED)),
    )


def visitors_by_day(start_date, end_date):
    """One row per expected date, newest first."""
    return list(
        Visitor.objects
        .filter(expected_date__range=(start_date, end_date))
        .values("expected_date")
        .annotate(
            registered=Count("id"),
            arrived=Count("id", filter=Q(entry_time__isnull=False)),
            cancelled=Count("id", filter=Q(status=Visitor.Status.CANCELLED)),
            expired=Count("id", filter=Q(status=Visitor.Status.EXPIRED)),
        )
        .order_by("-expected_date")
    )


def add_bar_widths(rows, value_key):
    """Add a percentage width to each row, for the CSS bars.

    The busiest day in the range becomes 100%; the rest are scaled against it.
    No chart library is involved: each bar is a div with a width.
    """
    if not rows:
        return rows
    largest = max(row[value_key] for row in rows) or 1
    for row in rows:
        row["bar_width"] = round(row[value_key] / largest * 100)
    return rows
