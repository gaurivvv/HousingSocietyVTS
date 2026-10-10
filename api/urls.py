"""API URL routing, mounted at /api/v1/ by config/urls.py."""

from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("vehicles/", views.vehicle_list, name="vehicle-list"),
    path("vehicles/lookup/", views.vehicle_lookup, name="vehicle-lookup"),
    path("gate/logs/", views.gate_log_list, name="gate-log-list"),
    path("gate/anpr-log/", views.gate_movement, name="gate-movement"),
]
