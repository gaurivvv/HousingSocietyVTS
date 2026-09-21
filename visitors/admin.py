from django.contrib import admin

from vehicles.utils import normalize_plate

from .models import Visitor


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = [
        "pass_code", "full_name", "phone", "flat", "resident",
        "vehicle_number", "expected_date", "status", "entry_time", "exit_time",
    ]
    list_filter = ["status", "expected_date", "flat__wing"]
    search_fields = ["full_name", "phone", "pass_code", "vehicle_number", "resident__full_name", "flat__flat_number"]
    date_hierarchy = "expected_date"
    list_select_related = ["flat__wing", "resident__flat__wing"]
    autocomplete_fields = ["flat", "resident"]

    fields = [
        "full_name", "phone", "flat", "resident", "vehicle_number",
        "expected_date", "status", "entry_time", "exit_time",
        "pass_code", "created_at", "updated_at",
    ]
    readonly_fields = ["pass_code", "created_at", "updated_at"]

    def get_search_results(self, request, queryset, search_term):
        # Normal search first, then also match the vehicle number in its stored format
        original_queryset = queryset
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        normalized = normalize_plate(search_term)
        if normalized:
            queryset |= original_queryset.filter(vehicle_number__icontains=normalized)
        return queryset, may_have_duplicates

    def has_delete_permission(self, request, obj=None):
        # Visitor records are part of the society's security history.
        return False
