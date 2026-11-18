"""rooms 路由（docs/04 §4.3）。

顺序很重要：``mine`` → 9 位 ``code`` → 数字 ``id``，避免 ``9 位寝室号``
被 ``int:id`` 抢先匹配。所有路由同时接受带/不带尾斜杠。
"""

from __future__ import annotations

from django.urls import re_path

from . import views

app_name = "rooms"

urlpatterns = [
    # 广场 / 我的寝室
    re_path(r"^rooms/?$", views.RoomSquareView.as_view(), name="square"),
    re_path(r"^rooms/mine/?$", views.RoomMineView.as_view(), name="mine"),
    # 详情：9 位 code 只读；数字 id 只用于 PATCH 与生命周期动作
    re_path(
        r"^rooms/(?P<code>\d{9})/?$",
        views.RoomDetailView.as_view(),
        name="detail-by-code",
    ),
    re_path(
        r"^rooms/(?P<room_id>\d+)/?$",
        views.RoomDetailView.as_view(),
        name="detail",
    ),
    # 生命周期动作
    re_path(
        r"^rooms/(?P<room_id>\d+)/lock/?$",
        views.RoomLockView.as_view(),
        name="lock",
    ),
    re_path(
        r"^rooms/(?P<room_id>\d+)/unlock/?$",
        views.RoomUnlockView.as_view(),
        name="unlock",
    ),
    re_path(
        r"^rooms/(?P<room_id>\d+)/dissolve/?$",
        views.RoomDissolveView.as_view(),
        name="dissolve",
    ),
    re_path(
        r"^rooms/(?P<room_id>\d+)/leave/?$",
        views.RoomLeaveView.as_view(),
        name="leave",
    ),
    re_path(
        r"^rooms/(?P<room_id>\d+)/members/(?P<uid>\d+)/?$",
        views.RoomMemberView.as_view(),
        name="member",
    ),
    # 房主转让
    re_path(
        r"^rooms/(?P<room_id>\d+)/transfer/?$",
        views.RoomTransferCreateView.as_view(),
        name="transfer-create",
    ),
    re_path(
        r"^room-transfers/(?P<transfer_id>\d+)/accept/?$",
        views.TransferAcceptView.as_view(),
        name="transfer-accept",
    ),
    re_path(
        r"^room-transfers/(?P<transfer_id>\d+)/decline/?$",
        views.TransferDeclineView.as_view(),
        name="transfer-decline",
    ),
    re_path(
        r"^room-transfers/(?P<transfer_id>\d+)/cancel/?$",
        views.TransferCancelView.as_view(),
        name="transfer-cancel",
    ),
    # 公开寝室页（免登录）
    re_path(
        r"^public/rooms/(?P<code>\d{9})/?$",
        views.PublicRoomView.as_view(),
        name="public",
    ),
]
