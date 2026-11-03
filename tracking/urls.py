from django.urls import path

from . import views

app_name = "tracking"

urlpatterns = [
    path("", views.gate, name="gate"),
    path("anpr-scan/", views.gate_anpr_scan, name="anpr_scan"),
    path("history/", views.gate_history, name="history"),
]
