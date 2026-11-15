"""通知路由（docs/04 §4.5）；同时接受带/不带尾斜杠。"""

from __future__ import annotations

from django.urls import re_path

from . import views

app_name = "notifications"

urlpatterns = [
    re_path(r"^notifications/?$", views.NotificationListView.as_view(), name="notification-list"),
    re_path(
        r"^notifications/unread-count/?$",
        views.NotificationUnreadCountView.as_view(),
        name="notification-unread-count",
    ),
    re_path(
        r"^notifications/read-all/?$",
        views.NotificationReadAllView.as_view(),
        name="notification-read-all",
    ),
    re_path(
        r"^notifications/(?P<pk>\d+)/read/?$",
        views.NotificationReadView.as_view(),
        name="notification-read",
    ),
]
