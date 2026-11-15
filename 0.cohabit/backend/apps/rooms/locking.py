"""rooms 加锁辅助（docs/02 §11.2/§11.4）。

全局锁顺序（任何写动作都必须遵守）：

1. ``TimeWindow``（``select_for_update``；无记录时不加锁）
2. 参与人 ``User``（按 id 升序）
3. 该寝在途 ``ConnectionRequest``（按 id 升序）
4. ``Room``（单行）
5. ``RoomTransfer``
6. ``RoomMember``（按 user_id 升序）
7. Notification / AuditLog 插入（不显式加锁）

本模块只负责“按顺序拿行锁”，不做业务判断；所有函数都要求调用方已经在
``transaction.atomic()`` 内，否则 PostgreSQL 会立即释放锁。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.utils import timezone

from apps.adminops.models import TimeWindow
from apps.core.timewindow import WindowClosed

from .models import Room, RoomMember, RoomTransfer


def _as_int_list(values: Iterable[Any] | None) -> list[int]:
    """去重+升序（锁顺序要求 id asc），忽略 ``None``。"""
    if not values:
        return []
    normalized: set[int] = set()
    for value in values:
        pk = getattr(value, "pk", value)
        if pk is None:
            continue
        normalized.add(int(pk))
    return sorted(normalized)


def lock_window(college: Any) -> TimeWindow | None:
    """锁住该学院的窗口行；无记录返回 ``None``（docs/02 §11.2 第 1 步）。"""
    if not college:
        return None
    return (
        TimeWindow.objects.select_for_update()
        .filter(college=str(college))
        .first()
    )


def require_locked_window(college: Any, at: Any = None) -> TimeWindow:
    """锁窗并校验开放；无记录/不在区间内抛 :class:`WindowClosed`。"""
    window = lock_window(college)
    now = at or timezone.now()
    if window is None or not (window.start_at <= now < window.end_at):
        raise WindowClosed()
    return window


def lock_users(user_ids: Iterable[Any] | None) -> list[Any]:
    """按 id 升序锁参与人（docs/02 §11.2 第 2 步）。"""
    ids = _as_int_list(user_ids)
    if not ids:
        return []
    from apps.accounts.models import User

    return list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


def lock_requests(request_ids: Iterable[Any] | None) -> list[Any]:
    """按 id 升序锁在途请求（docs/02 §11.2 第 3 步）。"""
    ids = _as_int_list(request_ids)
    if not ids:
        return []
    from apps.connections.models import ConnectionRequest

    return list(
        ConnectionRequest.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    )


def lock_room_row(room_id: Any) -> Room | None:
    """锁单行 Room（docs/02 §11.2 第 4 步）；不存在返回 ``None``。"""
    room_pk = getattr(room_id, "pk", room_id)
    if room_pk is None:
        return None
    return (
        Room.objects.select_for_update()
        .select_related("owner")
        .filter(pk=int(room_pk))
        .first()
    )


def lock_transfer(transfer_id: Any) -> RoomTransfer | None:
    """锁单行 RoomTransfer（docs/02 §11.2 第 5 步）。"""
    transfer_pk = getattr(transfer_id, "pk", transfer_id)
    if transfer_pk is None:
        return None
    return (
        RoomTransfer.objects.select_for_update()
        .select_related("room", "from_owner", "to_member")
        .filter(pk=int(transfer_pk))
        .first()
    )


def lock_pending_transfer(room: Room) -> RoomTransfer | None:
    """锁该寝当前 PENDING 转让（若有）。"""
    return (
        RoomTransfer.objects.select_for_update()
        .select_related("from_owner", "to_member")
        .filter(room_id=room.pk, status=RoomTransfer.Status.PENDING)
        .first()
    )


def lock_members(
    room_id: Any,
    user_ids: Iterable[Any] | None = None,
) -> list[RoomMember]:
    """按 user_id 升序锁成员行（docs/02 §11.2 第 6 步）。"""
    room_pk = getattr(room_id, "pk", room_id)
    if room_pk is None:
        return []
    queryset = RoomMember.objects.select_for_update().filter(room_id=int(room_pk))
    ids = _as_int_list(user_ids)
    if ids:
        queryset = queryset.filter(user_id__in=ids)
    return list(queryset.select_related("user").order_by("user_id"))


def open_request_ids(room: Room) -> list[int]:
    """该寝在途请求的 id（升序），用于“先锁请求再锁房间”。"""
    from apps.connections.models import OPEN_STATUSES, ConnectionRequest

    return list(
        ConnectionRequest.objects.filter(
            room_id=room.pk,
            status__in=OPEN_STATUSES,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def active_member_user_ids(room: Room) -> list[int]:
    """该寝 ACTIVE 成员的 user_id（升序），用于按序锁用户。"""
    return list(
        RoomMember.objects.filter(
            room_id=room.pk,
            status=RoomMember.Status.ACTIVE,
        )
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )
