from django.contrib import admin

from vehicles.utils import normalize_plate

from .models import VehicleLog


@admin.register(VehicleLog)
class VehicleLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "plate_number", "movement_type", "category", "vehicle", "owner"]
    list_filter = ["movement_type", "category", "timestamp"]
    search_fields = ["plate_number", "vehicle__resident__full_name", "remarks"]
    date_hierarchy = "timestamp"
    list_select_related = ["vehicle__resident"]

    # The vehicle is linked automatically from the plate, so it is shown but not edited
    fields = ["plate_number", "movement_type", "category", "timestamp", "remarks", "vehicle", "created_at"]
    readonly_fields = ["vehicle", "created_at"]

    @admin.display(description="Owner")
    def owner(self, obj):
        if obj.vehicle:
            return obj.vehicle.resident.full_name
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

    def has_delete_permission(self, request, obj=None):
        # Gate history is a security record: it is never deleted.
        return False
