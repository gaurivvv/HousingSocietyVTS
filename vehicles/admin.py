from django.contrib import admin
from django.utils import timezone

from .models import Vehicle
from .utils import normalize_plate


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["vehicle_number", "vehicle_type", "model_name", "colour", "resident", "is_active"]
    list_filter = ["is_active", "vehicle_type", "resident__flat__wing"]
    search_fields = ["vehicle_number", "model_name", "colour", "resident__full_name", "resident__phone"]
    list_select_related = ["resident__flat__wing"]
    autocomplete_fields = ["resident"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["mark_active", "mark_inactive"]

    def get_search_results(self, request, queryset, search_term):
        # First, the normal admin search (name, phone, model, colour, plate as typed).
        original_queryset = queryset
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        # Also match the plate in its stored format, e.g. "mh-12-ab" -> "MH12AB".
        normalized = normalize_plate(search_term)
        if normalized:
            queryset |= original_queryset.filter(vehicle_number__icontains=normalized)
        return queryset, may_have_duplicates

    @admin.action(description="Mark selected vehicles as active")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} vehicle(s) marked as active.")

    @admin.action(description="Mark selected vehicles as inactive")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} vehicle(s) marked as inactive.")