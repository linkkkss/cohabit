"""accounts 路由：认证端点与 /me（docs/04 §2、§4.1，契约路径无尾斜杠）。"""

from __future__ import annotations

from django.urls import re_path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    re_path(r"^auth/send-code/?$", views.SendCodeView.as_view(), name="send-code"),
    re_path(r"^auth/register/?$", views.RegisterView.as_view(), name="register"),
    re_path(r"^auth/login/?$", views.LoginView.as_view(), name="login"),
    re_path(r"^auth/refresh/?$", views.RefreshView.as_view(), name="refresh"),
    re_path(r"^auth/logout/?$", views.LogoutView.as_view(), name="logout"),
    re_path(r"^me/?$", views.MeView.as_view(), name="me"),
]
