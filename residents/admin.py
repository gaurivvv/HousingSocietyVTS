from django.contrib import admin
from django.utils import timezone

from .models import Resident


@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ["full_name", "flat", "resident_type", "phone", "email", "is_active"]
    list_filter = ["is_active", "resident_type", "flat__wing"]
    search_fields = ["full_name", "phone", "email", "flat__flat_number", "flat__wing__name"]
    list_select_related = ["flat__wing"]
    autocomplete_fields = ["flat"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["mark_active", "mark_inactive"]

    @admin.action(description="Mark selected residents as active")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} resident(s) marked as active.")

    @admin.action(description="Mark selected residents as inactive")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} resident(s) marked as inactive.")