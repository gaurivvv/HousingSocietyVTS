from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("residents/", include("residents.urls")),
    path("vehicles/", include("vehicles.urls")),
    path("", include("dashboard.urls")),
]
