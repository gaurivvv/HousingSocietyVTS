from django.contrib import admin

from vehicles.utils import normalize_plate

from .models import VehicleLog


@admin.register(VehicleLog)
class VehicleLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "plate_number", "movement_type", "category", "vehicle", "visitor", "owner", "recorded_by"]
    list_filter = ["movement_type", "category", "timestamp"]
    search_fields = [
        "plate_number",
        "vehicle__resident__full_name",
        "visitor__full_name",
        "visitor__pass_code",
        "remarks",
    ]
    date_hierarchy = "timestamp"
    list_select_related = ["vehicle__resident", "visitor__resident", "visitor__flat__wing"]

    # The vehicle and visitor are linked automatically from the plate, so they are shown but not edited
    fields = [
        "plate_number", "movement_type", "category", "timestamp", "remarks",
        "vehicle", "visitor", "recorded_by", "created_at",
    ]
    # recorded_by is read-only: it is set from the signed-in user in save_model(),
    # so it cannot be typed in or changed to someone else.
    readonly_fields = ["vehicle", "visitor", "recorded_by", "created_at"]

    @admin.display(description="Owner / host")
    def owner(self, obj):
        # Registered vehicle: its owner. Visitor vehicle: the resident being visited.
        if obj.vehicle:
            return obj.vehicle.resident.full_name
        if obj.visitor:
            return obj.visitor.resident.full_name
        return "-"

    def get_search_results(self, request, queryset, search_term):
        # Normal search first, then also match the plate in its stored format
        original_queryset = queryset
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        normalized = normalize_plate(search_term)
        if normalized:
            queryset |= original_queryset.filter(plate_number__icontains=normalized)
        return queryset, may_have_duplicates

    def save_model(self, request, obj, form, change):
        """Record who created this log, from the session rather than the form.

        Only set on creation. Editing an existing log does not rewrite who
        originally recorded it, which would falsify the audit trail.
        """
        if not change and obj.recorded_by_id is None:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        # Gate history is a security record: it is never deleted.
        return False
