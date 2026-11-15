"""画像路由（docs/04 §4.1/§4.2）；同时接受带/不带尾斜杠。"""

from __future__ import annotations

from django.urls import re_path

from apps.profiles import views

app_name = "profiles"

urlpatterns = [
    re_path(r"^me/profile/?$", views.ProfileMeView.as_view(), name="me-profile"),
    re_path(r"^me/contact/?$", views.ContactMeView.as_view(), name="me-contact"),
    re_path(r"^questionnaire/?$", views.QuestionnaireView.as_view(), name="questionnaire"),
    re_path(r"^users/(?P<uid>\d{10})/?$", views.PublicUserView.as_view(), name="user-detail"),
]
