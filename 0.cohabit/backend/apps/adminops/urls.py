"""adminops 学生端安全路由（docs/04 §4.6）：举报与拉黑。

``config/urls.py`` 以 ``path("api/", include(...))`` 挂载，故此处不带 ``api/`` 前缀；
``re_path`` 同时接受带/不带尾斜杠（与 accounts/rooms/connections 一致）。
"""

from __future__ import annotations

from django.urls import re_path

from . import views

app_name = "adminops"

urlpatterns = [
    re_path(r"^reports/?$", views.ReportCreateView.as_view(), name="report-create"),
    re_path(
        r"^blocks/?$",
        views.BlockCollectionView.as_view(),
        name="block-collection",
    ),
    re_path(
        r"^blocks/(?P<uid>[^/]+)/?$",
        views.BlockDetailView.as_view(),
        name="block-detail",
    ),
]
