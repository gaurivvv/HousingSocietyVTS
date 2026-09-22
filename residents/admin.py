from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from accounts.roles import RESIDENT

from .models import Resident


def eligible_resident_logins(resident=None):
    """Logins that may be linked to a resident.

    Only logins in the Resident group that are neither staff nor superusers,
    and that are not already linked to another resident.
    The login already linked to `resident` (if any) stays in the list.
    """
    logins = get_user_model().objects.filter(
        groups__name=RESIDENT, is_staff=False, is_superuser=False
    )
    not_linked_elsewhere = Q(resident__isnull=True)
    if resident is not None and resident.pk:
        not_linked_elsewhere |= Q(resident=resident)
    return logins.filter(not_linked_elsewhere).distinct().order_by("username")


class ResidentAdminForm(forms.ModelForm):
    """Admin form for residents: restricts which logins can be linked."""

    class Meta:
        model = Resident
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "user" in self.fields:
            # The same list limits both what is shown and what can be saved
            self.fields["user"].queryset = eligible_resident_logins(self.instance)
            self.fields["user"].label = "Login"
            self.fields["user"].help_text = (
                "Optional. Only logins in the Resident group that are not staff or superusers "
                "(and not linked to another resident) can be chosen. Choose the empty option to remove the link."
            )


@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    form = ResidentAdminForm
    list_display = ["full_name", "flat", "resident_type", "phone", "email", "user", "is_active"]
    list_filter = ["is_active", "resident_type", "flat__wing", ("user", admin.EmptyFieldListFilter)]
    search_fields = ["full_name", "phone", "email", "flat__flat_number", "flat__wing__name", "user__username"]
    list_select_related = ["flat__wing", "user"]
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
