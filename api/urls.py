"""API URL routing, mounted at /api/v1/ by config/urls.py."""

from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Auth & Identity
    path("auth/login/", views.auth_login, name="auth-login"),
    path("ping/", views.ping, name="ping"),

    # Vehicles & Gate
    path("vehicles/", views.vehicle_list, name="vehicle-list"),
    path("vehicles/lookup/", views.vehicle_lookup, name="vehicle-lookup"),
    path("gate/logs/", views.gate_log_list, name="gate-log-list"),
    path("gate/anpr-scan/", views.gate_anpr_scan, name="gate-anpr-scan"),
    path("gate/anpr-log/", views.gate_movement, name="gate-movement"),

    # Resident Portal (Mobile)
    path("resident/me/", views.resident_me, name="resident-me"),
    path("resident/visitors/", views.resident_create_visitor, name="resident-create-visitor"),

    # Guard Visitor Operations (Mobile)
    path("guard/visitors/", views.visitor_list_guard, name="guard-visitor-list"),
    path("visitors/<int:pk>/check-in/", views.visitor_check_in, name="visitor-check-in"),
    path("visitors/<int:pk>/check-out/", views.visitor_check_out, name="visitor-check-out"),

    # Overview & Metrics
    path("dashboard/stats/", views.dashboard_stats, name="dashboard-stats"),
]
