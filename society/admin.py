from django.contrib import admin

from .models import Flat, Wing


class FlatInline(admin.TabularInline):
    """Shows a wing's flats directly on the wing's edit page."""

    model = Flat
    extra = 0
    fields = ["flat_number"]
    show_change_link = True


@admin.register(Wing)
class WingAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "created_at"]
    search_fields = ["name"]
    inlines = [FlatInline]


@admin.register(Flat)
class FlatAdmin(admin.ModelAdmin):
    list_display = ["__str__", "wing", "flat_number", "created_at"]
    list_filter = ["wing"]
    search_fields = ["flat_number", "wing__name"]
    list_select_related = ["wing"]