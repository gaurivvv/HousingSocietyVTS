from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("residents/", include("residents.urls")),
    path("vehicles/", include("vehicles.urls")),
    path("gate/", include("tracking.urls")),
    path("visitors/", include("visitors.urls")),
    path("", include("dashboard.urls")),
]
