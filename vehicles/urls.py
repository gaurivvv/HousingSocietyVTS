from django.urls import path

from . import views

app_name = "vehicles"

urlpatterns = [
    path("", views.vehicle_list, name="vehicle_list"),
    path("add/", views.vehicle_create, name="vehicle_create"),
    path("<int:pk>/edit/", views.vehicle_update, name="vehicle_update"),
]
