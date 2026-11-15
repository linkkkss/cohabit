"""rooms 服务层：建寝/入寝原语 + 寝室写动作（docs/02 §4/§9/§11）。

约定：

* 每个公开写函数自己开 ``transaction.atomic()``；``create_room_for_pair`` /
  ``join_room_for_confirm`` / ``close_open_requests_for_room`` 允许被 connections
  的确认事务嵌套调用（``atomic`` 嵌套即 savepoint，语义安全）。
* 加锁严格按 docs/02 §11.2：窗口 → 用户（id 升序）→ 在途请求（id 升序）→
  寝室 → 转让 → 成员（user_id 升序）→ 通知/审计插入。
* 通知与审计都在同一事务内写入，不使用 ``on_commit``（docs/02 §9.3）。
* 业务错误一律抛 :mod:`apps.rooms.exceptions` 里的 ``ApiError`` 子类。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.adminops.models import Block
from apps.connections.models import OPEN_STATUSES, ConnectionRequest
from apps.core.audit import write_audit
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .exceptions import (
    ActionForbidden,
    AlreadyInRoom,
    CapacityInvalid,
    InvalidState,
    InvalidTarget,
    NotMember,
    NotOwner,
    OwnerMustTransferOrDissolve,
    RoomArchived,
    RoomDissolved,
    RoomFull,
    RoomLocked,
    RoomNotFound,
    RoomCodeGenerationFailed,
    TargetInRoom,
)
from .locking import (
    active_member_user_ids,
    lock_members,
    lock_pending_transfer,
    lock_requests,
    lock_room_row,
    lock_users,
    open_request_ids,
    require_locked_window,
)
from .models import Room, RoomMember, RoomTransfer
from .utils import (
    TAGS_MAX,
    TITLE_MAX_LENGTH,
    default_room_title,
    isoformat,
    merge_pair_tags,
    merge_tags,
    normalize_tags,
)

CAPACITY_CHOICES = (2, 4, 6)
ROOM_CODE_LENGTH = 9
ROOM_CODE_MAX_ATTEMPTS = 5
TRANSFER_TTL = timedelta(hours=24)

# 非终态（docs/02 §2.2）：只有这些状态允许读写寝室。
OPEN_ROOM_STATUSES = (
    Room.Status.RECRUITING,
    Room.Status.FULL,
    Room.Status.LOCKED,
)

# 终态（docs/02 §4.8/§4.9）：房间只读，原成员仍可查看历史详情。
TERMINAL_ROOM_STATUSES = (Room.Status.ARCHIVED, Room.Status.DISSOLVED)

# 关闭在途请求时的审计动作（docs/02 §9.2）。
CONNECTIONS_CLOSED_ACTIONS = {
    ConnectionRequest.CloseReason.FULL: "CONNECTION_CLOSED_FULL",
    ConnectionRequest.CloseReason.LOCKED: "CONNECTION_CLOSED_LOCKED",
    ConnectionRequest.CloseReason.ROOM_DISSOLVED: "CONNECTION_CLOSED_DISSOLVED",
    ConnectionRequest.CloseReason.ARCHIVED: "CONNECTION_CLOSED_ARCHIVED",
}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def generate_room_code() -> str:
    """生成 9 位数字且未被占用的寝室号；连续碰撞 5 次抛 500。"""
    for _ in range(ROOM_CODE_MAX_ATTEMPTS):
        code = str(secrets.randbelow(900_000_000) + 100_000_000)
        if len(code) == ROOM_CODE_LENGTH and not Room.objects.filter(code=code).exists():
            return code
    raise RoomCodeGenerationFailed()


def normalize_capacity(value: Any) -> int:
    """容量只允许 2/4/6；``None`` 回退到 4（docs/02 §4.1）。"""
    if value is None:
        return int(Room.Capacity.FOUR)
    try:
        capacity = int(value)
    except (TypeError, ValueError):
        raise CapacityInvalid(value) from None
    if capacity not in CAPACITY_CHOICES:
        raise CapacityInvalid(capacity)
    return capacity


def active_membership(user: User) -> RoomMember | None:
    """当前 ACTIVE 成员行（一个人最多一个 ACTIVE 寝室）。"""
    if getattr(user, "pk", None) is None:
        return None
    return (
        RoomMember.objects.select_related("room")
        .filter(user_id=user.pk, status=RoomMember.Status.ACTIVE)
        .first()
    )


def latest_terminal_membership(user: User) -> RoomMember | None:
    """最近一条终态寝室的历史成员行（``/api/rooms/mine`` 兜底展示用）。

    归档/解散后房间只读，但原成员仍可在“我的寝室”查看最终名单
    （docs/02 §4.8/§4.9/§4.10）。按房间归档时刻倒序，取最近一间。
    """
    if getattr(user, "pk", None) is None:
        return None
    return (
        RoomMember.objects.select_related("room", "room__owner")
        .prefetch_related("room__members__user")
        .filter(user_id=user.pk, room__status__in=TERMINAL_ROOM_STATUSES)
        .order_by(F("room__archived_at").desc(nulls_last=True), "-pk")
        .first()
    )


def _notify_members(
    room: Room,
    notification_type: str,
    payload: dict[str, Any] | None = None,
    *,
    exclude_user_ids: Any = (),
) -> None:
    """给房间所有 ACTIVE 成员发通知（可按 user_id 排除）。"""
    excluded = {int(pk) for pk in exclude_user_ids if pk is not None}
    member_rows = (
        RoomMember.objects.select_related("user")
        .filter(room_id=room.pk, status=RoomMember.Status.ACTIVE)
        .order_by("user_id")
    )
    for member in member_rows:
        if member.user_id in excluded:
            continue
        notify(member.user, notification_type, payload)


def _apply_status_after_member_loss(room: Room) -> None:
    """少一个人之后：FULL 降回 RECRUITING，其余状态保持（docs/02 §4.7）。"""
    if room.status == Room.Status.FULL:
        room.status = Room.Status.RECRUITING


def _save_room(room: Room, *fields: str) -> None:
    update_fields = list(fields)
    if "updated_at" not in update_fields:
        update_fields.append("updated_at")
    room.save(update_fields=update_fields)


def _close_request(
    request: ConnectionRequest,
    reason: str,
    *,
    actor: User | None,
    request_id: str,
    room_code: str,
) -> None:
    """关闭单条在途请求：CANCELLED + 通知双方 + 审计。"""
    request.status = ConnectionRequest.Status.CANCELLED
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
    payload = {
        "connection_id": request.pk,
        "reason": reason,
        "room_code": room_code,
    }
    for user in (request.initiator, request.target):
        notify(user, Notification.Type.SYSTEM, payload)
    write_audit(
        CONNECTIONS_CLOSED_ACTIONS.get(reason, "CONNECTION_CLOSED"),
        "connection",
        request.pk,
        actor=actor,
        meta={"room_id": request.room_id, "room_code": room_code, "reason": reason},
        request_id=request_id,
    )


def close_open_requests_for_room(
    room: Room,
    reason: str,
    except_request: ConnectionRequest | None = None,
    *,
    actor: User | None = None,
    request_id: str = "",
) -> int:
    """关闭该寝所有在途请求（INVITE room=this / APPLY room=this）。

    只关闭绑定本寝的请求，人-人邀请（``room IS NULL``）永不在这里被关闭
    （docs/02 §4.5）。返回关闭数量。
    """
    room_pk = getattr(room, "pk", room)
    room_code = getattr(room, "code", "") if not isinstance(room, int) else ""
    request_ids = list(
        ConnectionRequest.objects.filter(
            room_id=room_pk,
            status__in=OPEN_STATUSES,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    except_pk = getattr(except_request, "pk", except_request)
    if except_pk is not None:
        request_ids = [pk for pk in request_ids if pk != except_pk]
    if not request_ids:
        return 0

    locked = lock_requests(request_ids)
    closed = 0
    for request in locked:
        if getattr(except_request, "pk", None) == request.pk:
            continue
        if not room_code:
            room_code = request.room.code if request.room_id else ""
        _close_request(
            request,
            str(reason),
            actor=actor,
            request_id=request_id,
            room_code=room_code,
        )
        closed += 1
    return closed


# --------------------------------------------------------------------------- #
# 建寝 / 入寝原语（connections 确认流程调用）
# --------------------------------------------------------------------------- #
def create_room_for_pair(
    initiator: User,
    target: User,
    capacity_pref: Any = None,
    *,
    connection: ConnectionRequest | None = None,
    request_id: str = "",
    at: datetime | None = None,
) -> Room:
    """人-人 INVITE 二次确认后建寝（docs/02 §3.5.4 / §4.3）。

    * 容量 2 建寝即 FULL，容量 4/6 为 RECRUITING；
    * 标题 ``"{initiator.nickname}的寝室"``，标签为双方画像标签合并去重 ≤8；
    * 双方各得一条 CONFIRMED 通知；容量 2 时另发 ROOM_FULL。
    """
    now = at or timezone.now()
    capacity = normalize_capacity(capacity_pref)
    connection_id = getattr(connection, "pk", None)

    with transaction.atomic():
        require_locked_window(initiator.college, at=now)
        locked_users = {user.pk: user for user in lock_users([initiator.pk, target.pk])}
        initiator_row = locked_users.get(initiator.pk)
        target_row = locked_users.get(target.pk)
        if initiator_row is None or target_row is None:
            raise InvalidTarget("USER_NOT_FOUND", "寝室成员不存在")
        if initiator_row.status != User.Status.ACTIVE:
            raise ActionForbidden("账号已被禁用")
        if target_row.status != User.Status.ACTIVE:
            raise ActionForbidden("对方账号已被禁用", detail={"reason": "TARGET_DISABLED"})
        if initiator_row.gender != target_row.gender:
            raise ActionForbidden("性别不一致，无法组寝")
        if initiator_row.college != target_row.college:
            raise ActionForbidden("学院不一致，无法组寝")
        if active_membership(initiator_row) is not None:
            raise AlreadyInRoom(initiator_row.uid)
        if active_membership(target_row) is not None:
            raise TargetInRoom(target_row.uid)

        room = Room(
            code=generate_room_code(),
            title=default_room_title(initiator_row),
            owner=initiator_row,
            capacity=capacity,
            member_count=2,
            gender=initiator_row.gender,
            college=initiator_row.college,
            major=initiator_row.major or "",
            tags=merge_pair_tags(initiator_row, target_row),
            status=(
                Room.Status.FULL
                if capacity == 2
                else Room.Status.RECRUITING
            ),
        )
        try:
            with transaction.atomic():
                room.save(force_insert=True)
                owner_member = RoomMember.objects.create(
                    room=room,
                    user=initiator_row,
                    role=RoomMember.Role.OWNER,
                    status=RoomMember.Status.ACTIVE,
                )
                RoomMember.objects.create(
                    room=room,
                    user=target_row,
                    role=RoomMember.Role.MEMBER,
                    status=RoomMember.Status.ACTIVE,
                )
        except IntegrityError:
            raise TargetInRoom(target_row.uid) from None

        base_payload: dict[str, Any] = {
            "room_code": room.code,
            "room_title": room.title,
        }
        if connection_id is not None:
            base_payload["connection_id"] = connection_id
        notify(initiator_row, Notification.Type.CONFIRMED, base_payload)
        notify(target_row, Notification.Type.CONFIRMED, base_payload)
        if capacity == 2:
            full_payload = {"room_code": room.code, "capacity": room.capacity}
            notify(initiator_row, Notification.Type.ROOM_FULL, full_payload)
            notify(target_row, Notification.Type.ROOM_FULL, full_payload)

        meta: dict[str, Any] = {
            "capacity": room.capacity,
            "gender": room.gender,
            "college": room.college,
        }
        if connection_id is not None:
            meta["connection_id"] = connection_id
        write_audit(
            "ROOM_CREATED",
            "room",
            room.pk,
            actor=initiator_row,
            meta=meta,
            request_id=request_id,
        )
        # owner_member 只用于审计链路完整性，返回房间本身。
        _ = owner_member
        return room


def join_room_for_confirm(
    room: Room,
    user: User,
    request: ConnectionRequest | None = None,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> RoomMember:
    """房间邀请/申请二次确认后入寝（docs/02 §4.4）。

    锁 Room → 重读 member_count/status → 只允许 RECRUITING 且有容量；
    入寝后满员则转 FULL 并执行 §4.5 清理。
    """
    now = at or timezone.now()
    room_pk = getattr(room, "pk", room)
    college = getattr(room, "college", None)
    request_pk = getattr(request, "pk", request)

    with transaction.atomic():
        if college is None:
            existing = Room.objects.filter(pk=room_pk).only("college").first()
            college = existing.college if existing is not None else None
        if college:
            require_locked_window(college, at=now)

        participant_ids = [user.pk, getattr(room, "owner_id", None)]
        if request is not None:
            participant_ids.extend([request.initiator_id, request.target_id])
        lock_users([pk for pk in participant_ids if pk is not None])
        if request_pk is not None:
            lock_requests([request_pk])

        locked_room = lock_room_row(room_pk)
        if locked_room is None:
            raise RoomNotFound()
        _assert_joinable(locked_room)
        if RoomMember.objects.filter(
            room_id=locked_room.pk,
            user_id=user.pk,
            status=RoomMember.Status.ACTIVE,
        ).exists():
            raise AlreadyInRoom(user.uid)

        try:
            with transaction.atomic():
                member = RoomMember.objects.create(
                    room=locked_room,
                    user=user,
                    role=RoomMember.Role.MEMBER,
                    status=RoomMember.Status.ACTIVE,
                )
        except IntegrityError:
            raise AlreadyInRoom(user.uid) from None

        next_count = locked_room.member_count + 1
        _notify_members(
            locked_room,
            Notification.Type.MEMBER_JOINED,
            {
                "room_code": locked_room.code,
                "nickname": user.nickname,
                "member_count": next_count,
                "capacity": locked_room.capacity,
            },
            exclude_user_ids=[user.pk],
        )

        locked_room.member_count = next_count
        fields = ["member_count"]
        if next_count >= locked_room.capacity:
            locked_room.status = Room.Status.FULL
            fields.append("status")
        _save_room(locked_room, *fields)
        # lock_room_row() 返回的是另一个实例：同步调用方持有的 Room，
        # 否则 confirm 等外层响应会读到入寝前的 member_count/status。
        if isinstance(room, Room) and room is not locked_room:
            room.member_count = locked_room.member_count
            room.status = locked_room.status

        if locked_room.status == Room.Status.FULL:
            close_open_requests_for_room(
                locked_room,
                ConnectionRequest.CloseReason.FULL,
                actor=None,
                request_id=request_id,
            )
            _notify_members(
                locked_room,
                Notification.Type.ROOM_FULL,
                {"room_code": locked_room.code, "capacity": locked_room.capacity},
            )
            write_audit(
                "ROOM_FULL",
                "room",
                locked_room.pk,
                actor=None,
                meta={
                    "member_count": locked_room.member_count,
                    "capacity": locked_room.capacity,
                },
                request_id=request_id,
            )

        write_audit(
            "MEMBER_JOINED",
            "room_member",
            member.pk,
            actor=user,
            meta={
                "room_id": locked_room.pk,
                "user_id": user.pk,
                "role": RoomMember.Role.MEMBER,
            },
            request_id=request_id,
        )
        return member


def _assert_joinable(room: Room) -> None:
    """入寝前置校验（在锁住 Room 之后调用）。"""
    if room.status == Room.Status.ARCHIVED:
        raise RoomArchived(room.code)
    if room.status == Room.Status.DISSOLVED:
        raise RoomDissolved(room.code)
    if room.status == Room.Status.LOCKED:
        raise RoomLocked(room.code)
    if room.status == Room.Status.FULL:
        raise RoomFull(room.code)
    if room.status != Room.Status.RECRUITING:
        raise InvalidState("ROOM_STATUS")
    if room.member_count >= room.capacity:
        raise RoomFull(room.code)


# --------------------------------------------------------------------------- #
# 编辑 / 锁定 / 退出 / 移除 / 解散 / 归档
# --------------------------------------------------------------------------- #
def _load_room(room_id: Any) -> Room:
    room = (
        Room.objects.select_related("owner")
        .filter(pk=getattr(room_id, "pk", room_id))
        .first()
    )
    if room is None:
        raise RoomNotFound()
    return room


def _assert_owner(room: Room, actor: User) -> None:
    if room.owner_id != actor.pk:
        raise NotOwner()


def _is_admin(actor: User | None) -> bool:
    return bool(actor is not None and getattr(actor, "role", "") == User.Role.ADMIN)


def _assert_not_terminal(room: Room, *, reason: str = "ROOM_TERMINAL") -> None:
    if room.status == Room.Status.ARCHIVED:
        raise RoomArchived(room.code)
    if room.status == Room.Status.DISSOLVED:
        raise RoomDissolved(room.code)
    if room.status not in OPEN_ROOM_STATUSES:
        raise InvalidState(reason)


def update_room(
    actor: User,
    room_id: Any,
    *,
    title: Any = None,
    tags: Any = None,
    request_id: str = "",
) -> Room:
    """PATCH /api/rooms/:id：房主改标题/标签，逐字段审计（docs/02 §9.2）。

    不需要窗口开放（窗口只约束组寝写操作），终态直接 409 INVALID_STATE。
    """
    with transaction.atomic():
        lock_users([actor.pk])
        room = lock_room_row(room_id)
        if room is None:
            raise RoomNotFound()
        _assert_owner(room, actor)
        if room.status == Room.Status.ARCHIVED:
            raise InvalidState("ROOM_ARCHIVED")
        if room.status == Room.Status.DISSOLVED:
            raise InvalidState("ROOM_DISSOLVED")

        changed: list[str] = []
        if title is not None:
            text = str(title).strip()
            if not text:
                raise _validation("title", "标题不能为空")
            if len(text) > TITLE_MAX_LENGTH:
                raise _validation("title", f"标题最长 {TITLE_MAX_LENGTH} 字")
            if text != room.title:
                room.title = text
                changed.append("title")
        if tags is not None:
            normalized = normalize_tags(tags, limit=TAGS_MAX)
            if not isinstance(tags, (list, tuple)):
                raise _validation("tags", "tags 必须是字符串数组")
            if len(tags) > TAGS_MAX and len(normalized) > TAGS_MAX:
                raise _validation("tags", f"标签最多 {TAGS_MAX} 个")
            if normalized != list(room.tags or []):
                room.tags = normalized
                changed.append("tags")

        if not changed:
            return room

        _save_room(room, *changed)
        for field in changed:
            write_audit(
                "ROOM_UPDATED",
                "room",
                room.pk,
                actor=actor,
                meta={"fields": [field]},
                request_id=request_id,
            )
        return room


def _validation(field: str, message: str) -> Exception:
    from apps.accounts.exceptions import ApiError

    return ApiError(
        "VALIDATION_ERROR",
        message,
        status_code=400,
        detail={"fields": {field: [message]}},
    )


def lock_room(actor: User, room_id: Any, *, request_id: str = "") -> Room:
    """POST /api/rooms/:id/lock：RECRUITING → LOCKED 并关闭在途请求。"""
    with transaction.atomic():
        room = _load_room(room_id)
        require_locked_window(room.college)
        lock_users([actor.pk, room.owner_id])
        lock_requests(open_request_ids(room))
        locked_room = lock_room_row(room.pk)
        if locked_room is None:
            raise RoomNotFound()
        _assert_owner(locked_room, actor)
        _assert_not_terminal(locked_room, reason="ROOM_TERMINAL")
        if locked_room.status != Room.Status.RECRUITING:
            raise InvalidState("ROOM_NOT_RECRUITING")

        close_open_requests_for_room(
            locked_room,
            ConnectionRequest.CloseReason.LOCKED,
            actor=actor,
            request_id=request_id,
        )
        locked_room.status = Room.Status.LOCKED
        _save_room(locked_room, "status")
        _notify_members(
            locked_room,
            Notification.Type.ROOM_LOCKED,
            {"room_code": locked_room.code},
        )
        write_audit(
            "ROOM_LOCKED",
            "room",
            locked_room.pk,
            actor=actor,
            meta={"from": Room.Status.RECRUITING},
            request_id=request_id,
        )
        return locked_room


def unlock_room(actor: User, room_id: Any, *, request_id: str = "") -> Room:
    """POST /api/rooms/:id/unlock：LOCKED → RECRUITING，不补发通知。"""
    with transaction.atomic():
        room = _load_room(room_id)
        require_locked_window(room.college)
        lock_users([actor.pk, room.owner_id])
        lock_requests(open_request_ids(room))
        locked_room = lock_room_row(room.pk)
        if locked_room is None:
            raise RoomNotFound()
        _assert_owner(locked_room, actor)
        _assert_not_terminal(locked_room, reason="ROOM_TERMINAL")
        if locked_room.status != Room.Status.LOCKED:
            raise InvalidState("ROOM_NOT_LOCKED")

        locked_room.status = Room.Status.RECRUITING
        _save_room(locked_room, "status")
        write_audit(
            "ROOM_UNLOCKED",
            "room",
            locked_room.pk,
            actor=actor,
            meta={"to": Room.Status.RECRUITING},
            request_id=request_id,
        )
        return locked_room


def _cancel_pending_transfer_targeting(
    room: Room,
    user: User,
    *,
    actor: User | None,
    request_id: str,
    reason: str = "MEMBER_LEFT",
) -> RoomTransfer | None:
    """成员离寝/被移除时自动取消指向他的 PENDING 转让（docs/02 §6.4）。"""
    pending = lock_pending_transfer(room)
    if pending is None or pending.to_member_id != user.pk:
        return None
    pending.status = RoomTransfer.Status.CANCELLED
    pending.decided_at = timezone.now()
    pending.save(update_fields=["status", "decided_at", "updated_at"])
    payload = {
        "room_code": room.code,
        "transfer_id": pending.pk,
        "reason": reason,
    }
    for participant in (pending.from_owner, pending.to_member):
        notify(participant, Notification.Type.TRANSFER_CANCELLED, payload)
    write_audit(
        "TRANSFER_CANCELLED",
        "transfer",
        pending.pk,
        actor=actor,
        meta={"room_id": room.pk, "reason": reason},
        request_id=request_id,
    )
    return pending


def _leave_room(
    actor: User,
    room_id: Any,
    *,
    target_user_id: Any = None,
    request_id: str = "",
) -> RoomMember:
    """leave（target_user_id=None）与 remove（target_user_id=他人）共用实现。"""
    removing = target_user_id is not None
    with transaction.atomic():
        room = _load_room(room_id)
        require_locked_window(room.college)
        target = actor
        if removing:
            target = User.objects.filter(pk=target_user_id).first()
            if target is None:
                raise NotMember(detail={"reason": "USER_NOT_FOUND"})
        lock_users([actor.pk, target.pk, room.owner_id])
        lock_requests(open_request_ids(room))
        locked_room = lock_room_row(room.pk)
        if locked_room is None:
            raise RoomNotFound()
        _assert_not_terminal(locked_room, reason="ROOM_TERMINAL")
        if removing:
            _assert_owner(locked_room, actor)

        pending = _cancel_pending_transfer_targeting(
            locked_room,
            target,
            actor=actor,
            request_id=request_id,
        )
        _ = pending

        rows = lock_members(locked_room.pk, [target.pk])
        member = next(
            (
                row
                for row in rows
                if row.user_id == target.pk and row.status == RoomMember.Status.ACTIVE
            ),
            None,
        )
        if member is None:
            raise NotMember()

        if removing:
            if member.role == RoomMember.Role.OWNER:
                from .exceptions import CannotRemoveOwner

                raise CannotRemoveOwner()
            member.status = RoomMember.Status.REMOVED
            member.reason = RoomMember.Reason.REMOVED_BY_OWNER
            audit_action = "MEMBER_REMOVED"
            audit_meta = {
                "room_id": locked_room.pk,
                "target_user_id": target.pk,
                "reason": "REMOVED",
            }
            notify_reason = "REMOVED"
        else:
            if member.role == RoomMember.Role.OWNER:
                raise OwnerMustTransferOrDissolve()
            member.status = RoomMember.Status.LEFT
            member.reason = RoomMember.Reason.VOLUNTARY
            audit_action = "MEMBER_LEFT"
            audit_meta = {"room_id": locked_room.pk, "reason": "LEFT"}
            notify_reason = "LEFT"

        member.left_at = timezone.now()
        member.save(update_fields=["status", "reason", "left_at", "updated_at"])
        locked_room.member_count = max(locked_room.member_count - 1, 0)
        fields = ["member_count"]
        _apply_status_after_member_loss(locked_room)
        if "status" not in fields and locked_room.status != Room.Status.FULL:
            fields.append("status")
        _save_room(locked_room, *fields)

        payload = {
            "room_code": locked_room.code,
            "nickname": target.nickname,
            "reason": notify_reason,
        }
        _notify_members(
            locked_room,
            Notification.Type.MEMBER_LEFT,
            payload,
            exclude_user_ids=[],
        )
        notify(target, Notification.Type.MEMBER_LEFT, payload)
        write_audit(
            audit_action,
            "room_member",
            member.pk,
            actor=actor,
            meta=audit_meta,
            request_id=request_id,
        )
        return member


def leave_room(actor: User, room_id: Any, *, request_id: str = "") -> RoomMember:
    """POST /api/rooms/:id/leave：非房主主动退出（docs/02 §4.7）。"""
    return _leave_room(actor, room_id, request_id=request_id)


def remove_member(
    actor: User,
    room_id: Any,
    user_id: Any,
    *,
    request_id: str = "",
) -> RoomMember:
    """DELETE /api/rooms/:id/members/:uid：房主移除成员（docs/02 §4.7）。"""
    return _leave_room(actor, room_id, target_user_id=user_id, request_id=request_id)


def dissolve_room(
    actor: User,
    room_id: Any,
    *,
    reason: str = "DISSOLVED",
    force: bool = False,
    request_id: str = "",
) -> Room:
    """POST /api/rooms/:id/dissolve；Admin 走 force 分支不校验窗口。"""
    with transaction.atomic():
        room = _load_room(room_id)
        is_admin = _is_admin(actor)
        if not (force and is_admin):
            require_locked_window(room.college)
        lock_users([actor.pk, room.owner_id, *active_member_user_ids(room)])
        request_ids = set(open_request_ids(room))
        member_open = ConnectionRequest.objects.filter(
            status__in=OPEN_STATUSES,
        ).filter(Q(initiator_id__in=[actor.pk]) | Q(target_id__in=[actor.pk]))
        request_ids.update(member_open.order_by("pk").values_list("pk", flat=True))
        lock_requests(sorted(request_ids))
        locked_room = lock_room_row(room.pk)
        if locked_room is None:
            raise RoomNotFound()
        _assert_not_terminal(locked_room, reason="ROOM_TERMINAL")
        if not (force and is_admin):
            _assert_owner(locked_room, actor)

        close_open_requests_for_room(
            locked_room,
            ConnectionRequest.CloseReason.ROOM_DISSOLVED,
            actor=actor,
            request_id=request_id,
        )
        pending = lock_pending_transfer(locked_room)
        if pending is not None:
            pending.status = RoomTransfer.Status.CANCELLED
            pending.decided_at = timezone.now()
            pending.save(update_fields=["status", "decided_at", "updated_at"])
            payload = {
                "room_code": locked_room.code,
                "transfer_id": pending.pk,
                "reason": reason,
            }
            for participant in (pending.from_owner, pending.to_member):
                notify(participant, Notification.Type.TRANSFER_CANCELLED, payload)
            write_audit(
                "TRANSFER_CANCELLED",
                "transfer",
                pending.pk,
                actor=actor,
                meta={"room_id": locked_room.pk, "reason": reason},
                request_id=request_id,
            )

        members = lock_members(locked_room.pk)
        now = timezone.now()
        member_count = sum(
            1 for member in members if member.status == RoomMember.Status.ACTIVE
        )
        for member in members:
            if member.status != RoomMember.Status.ACTIVE:
                continue
            member.status = RoomMember.Status.LEFT
            member.reason = RoomMember.Reason.DISSOLVED
            member.left_at = now
            member.save(update_fields=["status", "reason", "left_at", "updated_at"])

        locked_room.member_count = 0
        locked_room.status = Room.Status.DISSOLVED
        locked_room.archived_at = now
        locked_room.dissolved_at = now
        _save_room(locked_room, "member_count", "status", "archived_at", "dissolved_at")

        notify_payload = {"room_code": locked_room.code, "reason": reason}
        for member in members:
            notify(member.user, Notification.Type.ROOM_DISSOLVED, notify_payload)

        action = "ROOM_FORCE_DISSOLVED" if force and is_admin else "ROOM_DISSOLVED"
        meta: dict[str, Any] = {"member_count": member_count}
        if action == "ROOM_DISSOLVED":
            meta["reason"] = reason
        write_audit(
            action,
            "room",
            locked_room.pk,
            actor=actor,
            meta=meta,
            request_id=request_id,
        )
        return locked_room


def archive_room(
    room_id: Any,
    *,
    window_end: datetime | None = None,
    actor: User | None = None,
    request_id: str = "",
) -> Room:
    """窗口结束归档（cron/admin，docs/02 §4.9）；DISSOLVED 跳过。"""
    with transaction.atomic():
        room = _load_room(room_id)
        lock_users([room.owner_id, *active_member_user_ids(room)])
        lock_requests(open_request_ids(room))
        locked_room = lock_room_row(room.pk)
        if locked_room is None:
            raise RoomNotFound()
        if locked_room.status == Room.Status.DISSOLVED:
            raise InvalidState("ROOM_DISSOLVED")
        if locked_room.status == Room.Status.ARCHIVED:
            raise InvalidState("ROOM_ARCHIVED")

        close_open_requests_for_room(
            locked_room,
            ConnectionRequest.CloseReason.ARCHIVED,
            actor=actor,
            request_id=request_id,
        )
        pending = lock_pending_transfer(locked_room)
        if pending is not None:
            pending.status = RoomTransfer.Status.CANCELLED
            pending.decided_at = timezone.now()
            pending.save(update_fields=["status", "decided_at", "updated_at"])
            payload = {
                "room_code": locked_room.code,
                "transfer_id": pending.pk,
                "reason": ConnectionRequest.CloseReason.ARCHIVED,
            }
            for participant in (pending.from_owner, pending.to_member):
                notify(participant, Notification.Type.TRANSFER_CANCELLED, payload)
            write_audit(
                "TRANSFER_CANCELLED",
                "transfer",
                pending.pk,
                actor=actor,
                meta={
                    "room_id": locked_room.pk,
                    "reason": ConnectionRequest.CloseReason.ARCHIVED,
                },
                request_id=request_id,
            )

        members = lock_members(locked_room.pk)
        now = timezone.now()
        for member in members:
            if member.status != RoomMember.Status.ACTIVE:
                continue
            member.status = RoomMember.Status.ARCHIVED
            member.reason = RoomMember.Reason.ARCHIVED
            member.left_at = now
            member.save(update_fields=["status", "reason", "left_at", "updated_at"])

        member_count = locked_room.member_count
        locked_room.status = Room.Status.ARCHIVED
        locked_room.archived_at = now
        _save_room(locked_room, "status", "archived_at")

        payload = {
            "room_code": locked_room.code,
            "archived_at": isoformat(now),
        }
        for member in members:
            notify(member.user, Notification.Type.ROOM_ARCHIVED, payload)

        meta: dict[str, Any] = {"member_count": member_count}
        if window_end is not None:
            meta["window_end"] = isoformat(window_end)
        write_audit(
            "ROOM_ARCHIVED",
            "room",
            locked_room.pk,
            actor=actor,
            meta=meta,
            request_id=request_id,
        )
        return locked_room


def repair_member_count(room_id: Any = None) -> dict[str, int]:
    """按 ACTIVE 成员行修复 ``Room.member_count``（对账/回归工具）。"""
    rooms = Room.objects.all() if room_id is None else Room.objects.filter(pk=room_id)
    checked = 0
    repaired = 0
    with transaction.atomic():
        for room in rooms.iterator():
            checked += 1
            actual = RoomMember.objects.filter(
                room_id=room.pk,
                status=RoomMember.Status.ACTIVE,
            ).count()
            if actual != room.member_count:
                before = room.member_count
                room.member_count = actual
                _save_room(room, "member_count")
                repaired += 1
                write_audit(
                    "ROOM_MEMBER_COUNT_REPAIRED",
                    "room",
                    room.pk,
                    meta={"before": before, "after": actual},
                )
    return {"checked": checked, "repaired": repaired}


# --------------------------------------------------------------------------- #
# 查询选择器（视图层使用）
# --------------------------------------------------------------------------- #
def _blocked_user_ids(viewer: User) -> set[int]:
    if getattr(viewer, "pk", None) is None:
        return set()
    pairs = Block.objects.filter(
        Q(blocker_id=viewer.pk) | Q(blocked_id=viewer.pk)
    ).values_list("blocker_id", "blocked_id")
    blocked: set[int] = set()
    for blocker_id, blocked_id in pairs:
        blocked.add(blocked_id if blocker_id == viewer.pk else blocker_id)
    return blocked


def square_rooms(
    viewer: User,
    *,
    major: str | None = None,
    capacity: int | None = None,
    tags: list[str] | None = None,
) -> QuerySet[Room]:
    """广场：同学院同性别、仅 RECRUITING 且有空位（docs/02 §4.10）。"""
    queryset = (
        Room.objects.filter(
            status=Room.Status.RECRUITING,
            member_count__lt=F("capacity"),
            college=viewer.college,
            gender=viewer.gender,
        )
        .select_related("owner")
        .prefetch_related("members__user")
    )
    # 有寝室历史（含 LEFT/REMOVED/ARCHIVED）都不能再进同一个房间（R-13），
    # 广场直接不展示这些房间，避免用户点了才报错。
    visited = RoomMember.objects.filter(user_id=viewer.pk).values("room_id")
    queryset = queryset.exclude(pk__in=visited)
    blocked = _blocked_user_ids(viewer)
    if blocked:
        queryset = queryset.exclude(owner_id__in=blocked)
    if major:
        queryset = queryset.filter(major=major)
    if capacity is not None:
        queryset = queryset.filter(capacity=normalize_capacity(capacity))
    for tag in tags or []:
        queryset = queryset.filter(tags__contains=[tag])
    return queryset.order_by("-created_at", "-id")


def get_room_for_viewer(
    viewer: User,
    *,
    code: Any = None,
    room_id: Any = None,
) -> tuple[Room, RoomMember | None]:
    """详情可见性（docs/02 §4.10）：成员随时可看；终态房间对原成员只读可见。

    * ACTIVE 成员：直接返回 ``room, membership``；
    * 终态（ARCHIVED/DISSOLVED）房间：该用户存在 ``RoomMember`` 历史记录即可读，
      actions 由 serializer 依终态全部置 false；
    * 非终态房间的前成员（LEFT/REMOVED）：仍 404（R-13 不可重进、不泄露）；
    * 非成员需同学院同性别且房间非终态；被拉黑一律 404。
    """
    queryset = Room.objects.select_related("owner").prefetch_related("members__user")
    if code is not None:
        room = queryset.filter(code=str(code)).first()
    else:
        room = queryset.filter(pk=room_id).first()
    if room is None:
        raise RoomNotFound()

    membership = RoomMember.objects.filter(room_id=room.pk, user_id=viewer.pk).first()
    if membership is not None and membership.status == RoomMember.Status.ACTIVE:
        return room, membership
    if getattr(viewer, "pk", None) in _blocked_user_ids(room.owner):
        raise RoomNotFound()
    if room.status in TERMINAL_ROOM_STATUSES:
        if membership is not None:
            # 原成员保留只读历史（docs/02 §4.8/§4.9）；公开页仍 404。
            return room, membership
        raise RoomNotFound()
    if membership is not None:
        # 曾经是成员但已离开/被移除：非终态房间不再可见（R-13 不可重进）。
        raise RoomNotFound()
    if viewer.college != room.college or viewer.gender != room.gender:
        raise RoomNotFound()
    return room, None


def public_room(code: Any) -> Room:
    """公开房间页：仅 RECRUITING/FULL/LOCKED，其余 404（docs/04 §4.3）。"""
    room = (
        Room.objects.select_related("owner")
        .prefetch_related("members__user")
        .filter(code=str(code))
        .first()
    )
    if room is None or room.status not in OPEN_ROOM_STATUSES:
        raise RoomNotFound()
    return room


def room_memberships(viewer: User) -> RoomMember | None:
    """``/api/rooms/mine`` 用的当前成员行。"""
    return active_membership(viewer)


def merge_room_tags(*groups: Any) -> list[str]:
    """给 views/serializers 复用的标签合并小工具。"""
    return merge_tags(*groups)


def touch_room(room: Room) -> None:
    """更新 ``updated_at``（仅用于需要刷新的场景）。"""
    room.save(update_fields=["updated_at"])
