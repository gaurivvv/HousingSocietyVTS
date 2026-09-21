from django.urls import path

from . import views

app_name = "residents"

urlpatterns = [
    path("", views.resident_list, name="resident_list"),
    path("add/", views.resident_create, name="resident_create"),
]
