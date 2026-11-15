"""匹配路由（docs/04 §4.2）；同时接受带/不带尾斜杠。"""

from __future__ import annotations

from django.urls import re_path

from apps.matching import views

app_name = "matching"

urlpatterns = [
    re_path(r"^match/?$", views.MatchListView.as_view(), name="match-list"),
    re_path(
        r"^match/(?P<uid>\d{10})/score/?$",
        views.MatchScoreView.as_view(),
        name="match-score",
    ),
    re_path(
        r"^match/(?P<uid>\d{10})/?$",
        views.MatchDetailView.as_view(),
        name="match-detail",
    ),
]
