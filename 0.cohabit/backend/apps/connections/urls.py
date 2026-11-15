"""connections 路由（docs/04 §4.4）；动作段优先于详情，尾斜杠可选。"""

from __future__ import annotations

from django.urls import re_path

from . import views

app_name = "connections"

urlpatterns = [
    re_path(
        r"^connections/?$",
        views.ConnectionCollectionView.as_view(),
        name="list",
    ),
    re_path(
        r"^connections/(?P<connection_id>\d+)/accept/?$",
        views.ConnectionAcceptView.as_view(),
        name="accept",
    ),
    re_path(
        r"^connections/(?P<connection_id>\d+)/decline/?$",
        views.ConnectionDeclineView.as_view(),
        name="decline",
    ),
    re_path(
        r"^connections/(?P<connection_id>\d+)/cancel/?$",
        views.ConnectionCancelView.as_view(),
        name="cancel",
    ),
    re_path(
        r"^connections/(?P<connection_id>\d+)/confirm/?$",
        views.ConnectionConfirmView.as_view(),
        name="confirm",
    ),
    re_path(
        r"^connections/(?P<connection_id>\d+)/?$",
        views.ConnectionDetailView.as_view(),
        name="detail",
    ),
]
