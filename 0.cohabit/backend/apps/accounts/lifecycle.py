"""账号生命周期：逻辑删除/禁用级联（docs/04 §4.1、docs/02 X-35/X-51）。

``disable_account`` 是学生自助注销与 Admin 禁用共用的唯一入口：

* open 请求 → ``CANCELLED / USER_DISABLED``；
* 房主 → 强制解散寝室（房间 ``DISSOLVED``，成员 ``LEFT / DISSOLVED``）；
* 普通成员 → ``LEFT / USER_DISABLED``，房态按 docs/02 §4.7 回退；
* 取消与本人相关的待处理房主转让；
* 清空联系方式，逻辑删除用户（``status=DISABLED``、``is_active=False``、
  邮箱匿名化），保留历史数据。

整个级联与审计在同一事务内完成（docs/06 S-10）；通知/审计任一失败都会回滚。
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

DISABLED_EMAIL_TEMPLATE = "anon{pk}@deleted.local"

# docs/02 §9.2：禁用清理使用专用审计动作，房间解散沿用解散清理动作。
_CLOSE_REQUEST_ACTIONS = {
    "USER_DISABLED": "CONNECTION_USER_DISABLED",
    "ROOM_DISSOLVED": "CONNECTION_CLOSED_DISSOLVED",
}


def _notify_both(request, reason: str, room_code: str) -> None:
    from apps.notifications.models import Notification
    from apps.notifications.services import notify

    payload = {
        "connection_id": request.pk,
        "reason": reason,
        "room_code": room_code,
    }
    for user in (request.initiator, request.target):
        notify(user, Notification.Type.SYSTEM, payload)


def _close_request(
    request,
    reason: str,
    *,
    actor,
    request_id: str,
    room_code: str = "",
    disabled_user_id: int | None = None,
) -> None:
    """关闭一条在途请求：CANCELLED + 双方通知 + 审计（docs/02 §9.2）。"""
    from apps.core.audit import write_audit

    request.status = "CANCELLED"
    request.close_reason = reason
    request.closed_by = actor
    request.version = (request.version or 0) + 1
    request.save(
        update_fields=[
            "status",
            "close_reason",
            "closed_by",
            "version",
            "updated_at",
        ]
    )
    _notify_both(request, reason, room_code or "")
    meta: dict[str, Any] = {
        "room_id": request.room_id,
        "reason": reason,
    }
    if disabled_user_id is not None:
        meta["disabled_user_id"] = disabled_user_id
    write_audit(
        _CLOSE_REQUEST_ACTIONS.get(reason, "CONNECTION_CLOSED"),
        "connection",
        request.pk,
        actor=actor,
        meta=meta,
        request_id=request_id,
    )


def _close_open_requests(user, *, actor, request_id: str) -> int:
    """关闭所有与用户相关的 open 请求（发起或接收）。"""
    from apps.connections.models import OPEN_STATUSES, ConnectionRequest

    requests = list(
        ConnectionRequest.objects.select_for_update()
        .filter(status__in=OPEN_STATUSES)
        .filter(Q(initiator=user) | Q(target=user))
        .select_related("initiator", "target")
        .order_by("pk")
    )
    for request in requests:
        room_code = request.room.code if request.room_id else ""
        _close_request(
            request,
            "USER_DISABLED",
            actor=actor,
            request_id=request_id,
            room_code=room_code,
            disabled_user_id=user.pk,
        )
    return len(requests)


def _cancel_transfer(transfer, reason: str, *, actor, request_id: str, now) -> None:
    """取消一笔待处理转让并通知双方（docs/02 §9.2 TRANSFER_CANCELLED）。"""
    from apps.core.audit import write_audit
    from apps.notifications.models import Notification
    from apps.notifications.services import notify

    transfer.status = "CANCELLED"
    transfer.decided_at = now
    transfer.save(update_fields=["status", "decided_at", "updated_at"])
    payload = {
        "room_code": transfer.room.code,
        "transfer_id": transfer.pk,
        "reason": reason,
    }
    for user in (transfer.from_owner, transfer.to_member):
        notify(user, Notification.Type.TRANSFER_CANCELLED, payload)
    write_audit(
        "TRANSFER_CANCELLED",
        "transfer",
        transfer.pk,
        actor=actor,
        meta={"room_id": transfer.room_id, "reason": reason},
        request_id=request_id,
    )


def _drain_pending_transfers(queryset, *, reason, actor, request_id, now) -> int:
    transfers = list(
        queryset.select_for_update()
        .select_related("room", "from_owner", "to_member")
        .order_by("pk")
    )
    for transfer in transfers:
        _cancel_transfer(
            transfer,
            reason,
            actor=actor,
            request_id=request_id,
            now=now,
        )
    return len(transfers)


def _dissolve_room(
    room,
    *,
    disabled_user,
    actor,
    request_id: str,
    now,
) -> int:
    """房主被禁用：强制解散寝室并清理全部在途关系（docs/02 X-35）。"""
    from apps.connections.models import OPEN_STATUSES, ConnectionRequest
    from apps.core.audit import write_audit
    from apps.notifications.models import Notification
    from apps.notifications.services import notify
    from apps.rooms.models import RoomMember, RoomTransfer

    # 先清理绑定在该寝室的在途请求（可能包含其他成员发起的请求）。
    room_requests = list(
        ConnectionRequest.objects.select_for_update()
        .filter(room_id=room.pk, status__in=OPEN_STATUSES)
        .select_related("room", "initiator", "target")
        .order_by("pk")
    )
    for request in room_requests:
        _close_request(
            request,
            "ROOM_DISSOLVED",
            actor=actor,
            request_id=request_id,
            room_code=room.code,
        )

    cancelled = _drain_pending_transfers(
        RoomTransfer.objects.filter(room_id=room.pk, status="PENDING"),
        reason="ROOM_DISSOLVED",
        actor=actor,
        request_id=request_id,
        now=now,
    )

    members = list(
        RoomMember.objects.select_for_update()
        .filter(room_id=room.pk, status="ACTIVE")
        .select_related("user")
        .order_by("pk")
    )
    recipients = [member.user for member in members]
    for member in members:
        member.status = "LEFT"
        member.reason = "DISSOLVED"
        member.left_at = now
        member.save(update_fields=["status", "reason", "left_at", "updated_at"])

    member_count = len(members)
    room.member_count = 0
    room.status = "DISSOLVED"
    room.archived_at = now
    room.dissolved_at = now
    room.save(
        update_fields=[
            "member_count",
            "status",
            "archived_at",
            "dissolved_at",
            "updated_at",
        ]
    )

    payload = {"room_code": room.code, "reason": "USER_DISABLED"}
    for user in recipients:
        notify(user, Notification.Type.ROOM_DISSOLVED, payload)

    is_admin_action = actor is not None and getattr(actor, "pk", None) != disabled_user.pk
    write_audit(
        "ROOM_FORCE_DISSOLVED" if is_admin_action else "ROOM_DISSOLVED",
        "room",
        room.pk,
        actor=actor,
        meta={"member_count": member_count, "reason": "USER_DISABLED"},
        request_id=request_id,
    )
    return cancelled


def _leave_room(
    room,
    membership,
    *,
    disabled_user,
    actor,
    request_id: str,
    now,
) -> int:
    """普通成员被禁用：LEFT / USER_DISABLED，房态回退（docs/02 X-31）。"""
    from apps.core.audit import write_audit
    from apps.notifications.models import Notification
    from apps.notifications.services import notify
    from apps.rooms.models import RoomMember, RoomTransfer

    cancelled = _drain_pending_transfers(
        RoomTransfer.objects.filter(room_id=room.pk, to_member=disabled_user, status="PENDING"),
        reason="USER_DISABLED",
        actor=actor,
        request_id=request_id,
        now=now,
    )

    recipients = [
        member.user
        for member in RoomMember.objects.select_related("user")
        .filter(room_id=room.pk, status="ACTIVE")
        .order_by("pk")
    ]
    membership.status = "LEFT"
    membership.reason = "USER_DISABLED"
    membership.left_at = now
    membership.save(update_fields=["status", "reason", "left_at", "updated_at"])

    room.member_count = max(room.member_count - 1, 0)
    if room.status == "FULL":
        room.status = "RECRUITING"
    room.save(update_fields=["member_count", "status", "updated_at"])

    payload = {
        "room_code": room.code,
        "nickname": disabled_user.nickname,
        "reason": "USER_DISABLED",
    }
    for user in recipients:
        if user.pk == disabled_user.pk:
            continue
        notify(user, Notification.Type.MEMBER_LEFT, payload)

    write_audit(
        "MEMBER_LEFT",
        "room_member",
        membership.pk,
        actor=actor,
        meta={"room_id": room.pk, "reason": "USER_DISABLED"},
        request_id=request_id,
    )
    return cancelled


def _handle_rooms(user, *, actor, request_id: str, now) -> dict[str, int]:
    """处理用户作为房主/成员的 ACTIVE 寝室，返回级联计数。"""
    from apps.rooms.models import Room, RoomMember

    memberships = list(
        RoomMember.objects.select_for_update()
        .filter(user_id=user.pk, status="ACTIVE")
        .order_by("pk")
    )
    owner_room_ids = list(
        Room.objects.filter(owner_id=user.pk, status__in=["RECRUITING", "FULL", "LOCKED"])
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    room_ids = {membership.room_id for membership in memberships} | set(owner_room_ids)
    rooms = {
        room.pk: room
        for room in Room.objects.select_for_update()
        .select_related("owner")
        .filter(pk__in=room_ids)
        .order_by("pk")
    }

    stats = {"rooms_dissolved": 0, "rooms_left": 0, "transfers": 0}
    handled: set[int] = set()
    for membership in memberships:
        room = rooms.get(membership.room_id)
        if room is None or room.pk in handled:
            continue
        handled.add(room.pk)
        if room.owner_id == user.pk:
            stats["transfers"] += _dissolve_room(
                room,
                disabled_user=user,
                actor=actor,
                request_id=request_id,
                now=now,
            )
            stats["rooms_dissolved"] += 1
        else:
            stats["transfers"] += _leave_room(
                room,
                membership,
                disabled_user=user,
                actor=actor,
                request_id=request_id,
                now=now,
            )
            stats["rooms_left"] += 1

    # 兜底：用户是房主但成员关系缺失（不应出现），仍强制解散。
    for room_id in owner_room_ids:
        if room_id in handled:
            continue
        room = rooms.get(room_id)
        if room is None:
            continue
        stats["transfers"] += _dissolve_room(
            room,
            disabled_user=user,
            actor=actor,
            request_id=request_id,
            now=now,
        )
        stats["rooms_dissolved"] += 1
    return stats


def _clear_contact_info(user) -> None:
    """清空联系方式明文（手册 D9、docs/03 §1.3.2）。"""
    from apps.accounts.models import ContactInfo

    ContactInfo.objects.filter(user_id=user.pk).update(
        qq=None,
        wechat=None,
        phone=None,
        show_qq=False,
        show_wechat=False,
        show_phone=False,
        updated_at=timezone.now(),
    )


def disable_account(
    user,
    *,
    actor=None,
    request_id: str = "",
    reason: str = "USER_DISABLED",
):
    """禁用/逻辑删除账号并返回最新用户实例。

    可重复调用：已处于 ``DISABLED + 非 active`` 的账号直接返回，不会重复级联。
    ``actor`` 为 Admin 操作者；学生自助注销时传本人。
    """
    from .models import User

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.status == User.Status.DISABLED and not locked_user.is_active:
            return locked_user

        now = timezone.now()
        cascade = {
            "connections": _close_open_requests(
                locked_user, actor=actor, request_id=request_id
            )
        }
        cascade.update(
            _handle_rooms(locked_user, actor=actor, request_id=request_id, now=now)
        )

        # 兜底：与本人相关、但不在已处理寝室范围内的待处理转让。
        from apps.rooms.models import RoomTransfer

        cascade["transfers"] += _drain_pending_transfers(
            RoomTransfer.objects.filter(status="PENDING").filter(
                Q(from_owner=locked_user) | Q(to_member=locked_user)
            ),
            reason="USER_DISABLED",
            actor=actor,
            request_id=request_id,
            now=now,
        )

        _clear_contact_info(locked_user)
        locked_user.status = User.Status.DISABLED
        locked_user.is_active = False
        locked_user.email = DISABLED_EMAIL_TEMPLATE.format(pk=locked_user.pk)
        locked_user.save(update_fields=["status", "is_active", "email", "updated_at"])

        from apps.core.audit import write_audit

        write_audit(
            "USER_DISABLED",
            "user",
            locked_user.pk,
            actor=actor,
            meta={"reason": reason, "cascade": cascade},
            request_id=request_id,
        )
        return locked_user
