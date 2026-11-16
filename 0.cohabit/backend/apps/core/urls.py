from django.urls import re_path

from .views import admin_stats, health_check, timewindow_status

app_name = "core"

urlpatterns = [
    re_path(r"^health/?$", health_check, name="health"),
    re_path(r"^timewindow/?$", timewindow_status, name="timewindow-status"),
    re_path(r"^admin/stats/?$", admin_stats, name="admin-stats"),
]
