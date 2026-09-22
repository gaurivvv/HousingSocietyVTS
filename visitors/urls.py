from django.urls import path

from . import views

app_name = "visitors"

urlpatterns = [
    path("", views.visitor_list, name="visitor_list"),
    path("add/", views.visitor_create, name="visitor_create"),
    path("<int:pk>/", views.visitor_detail, name="visitor_detail"),
    path("<int:pk>/check-in/", views.visitor_check_in, name="visitor_check_in"),
    path("<int:pk>/check-out/", views.visitor_check_out, name="visitor_check_out"),
    path("<int:pk>/cancel/", views.visitor_cancel, name="visitor_cancel"),
]
