"""connections 服务层：邀请/申请的创建、接受、拒绝、撤回、二次确认与过期。

约定（docs/02 §3、§11）：

* 每个写动作一个 ``transaction.atomic()``，状态/通知/审计同事务，不用 ``on_commit``；
* 锁顺序：TimeWindow → User（id asc）→ 在途 ConnectionRequest（id asc）→ Room；
* 建寝/入寝不在这里重新实现，直接调用 ``apps.rooms.services`` 的原语；
* 懒过期：写操作在锁内把 ``expires_at <= now`` 的在途请求关闭为
  ``EXPIRED/TIMEOUT``，然后抛 ``409 REQUEST_EXPIRED``（写要提交，故在事务外抛）。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.adminops.models import Block
from apps.core.audit import write_audit
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.profiles.completeness import missing_profile_parts
from apps.profiles.services import get_profile, profile_is_complete
from apps.rooms import services as room_services
from apps.rooms.exceptions import (
    RoomArchived,
    RoomDissolved,
    RoomFull,
    RoomLocked,
    RoomNotFound,
)
from apps.rooms.locking import (
    lock_requests,
    lock_room_row,
    lock_users,
    lock_window,
    require_locked_window,
)
from apps.rooms.models import Room, RoomMember
from apps.rooms.utils import isoformat

from .exceptions import (
    AccountDisabled,
    ActionForbidden,
    AlreadyConfirmed,
    AlreadyInRoom,
    Blocked,
    CapacityInvalid,
    ConnectionNotFound,
    Cooldown,
    DuplicateRequest,
    InvalidState,
    InvalidTarget,
    InvalidType,
    ProfileIncomplete,
    RateLimited,
    RequestClosed,
    RequestExpired,
    SelfRequest,
    TargetInRoom,
    TargetProfileIncomplete,
    UserNotFound,
    WrongCollege,
    WrongGender,
)
from .models import OPEN_STATUSES, ConnectionRequest

# 超时口径（docs/02 §3.6）。
PENDING_TTL = timedelta(hours=48)
CONTACT_TTL = timedelta(days=7)
CONFIRM_TTL = timedelta(hours=48)

# 限频口径（docs/02 §3.9、§12.6）。
IN_FLIGHT_LIMIT = 3
DAILY_LIMIT = 10
COOLDOWN = timedelta(hours=24)

MESSAGE_MAX_LENGTH = 200
_INBOX_ALIASES = frozenset({"inbox", "incoming", "received"})
_SENT_ALIASES = frozenset({"sent", "outbox", "outgoing", "send"})


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _now(at: datetime | None = None) -> datetime:
    if at is None:
        return timezone.now()
    if timezone.is_naive(at):
        return timezone.make_aware(at, timezone.get_current_timezone())
    return at


def _day_start(now: datetime) -> datetime:
    """按项目时区（Asia/Shanghai）取当天 00:00（docs/02 §3.9）。"""
    local = timezone.localtime(now)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _open_request_ids_for(user_ids: list[int]) -> list[int]:
    return list(
        ConnectionRequest.objects.filter(
            Q(initiator_id__in=user_ids) | Q(target_id__in=user_ids),
            status__in=OPEN_STATUSES,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def _open_request_ids_for_room(room_id: int | None) -> list[int]:
    if room_id is None:
        return []
    return list(
        ConnectionRequest.objects.filter(
            room_id=room_id,
            status__in=OPEN_STATUSES,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def _active_membership(user: Any) -> RoomMember | None:
    pk = getattr(user, "pk", None)
    if pk is None:
        return None
    return RoomMember.objects.filter(
        user_id=pk,
        status=RoomMember.Status.ACTIVE,
    ).first()


def _is_blocked(first_id: int, second_id: int) -> bool:
    return Block.objects.filter(
        Q(blocker_id=first_id, blocked_id=second_id)
        | Q(blocker_id=second_id, blocked_id=first_id)
    ).exists()


def _profile_state(user: Any) -> tuple[int, list[str]]:
    """返回 ``(completeness, missing)``；无画像视为 0 分。"""
    profile = get_profile(user)
    if profile is None:
        return 0, ["profile"]
    completeness = int(profile.completeness or 0)
    if completeness >= 100:
        return completeness, []
    missing = missing_profile_parts(
        user,
        profile.hard_answers,
        profile.soft_answers,
        profile.red_lines_confirmed,
        profile.tags,
        profile.prompts,
    )
    return completeness, missing


def _assert_self_profile_complete(user: Any) -> None:
    profile = get_profile(user)
    if profile_is_complete(profile):
        return
    completeness, missing = _profile_state(user)
    raise ProfileIncomplete(completeness, missing)


def _assert_target_profile_complete(user: Any) -> None:
    profile = get_profile(user)
    if profile_is_complete(profile):
        return
    completeness, _ = _profile_state(user)
    raise TargetProfileIncomplete(completeness)


def _assert_account_active(user: Any) -> None:
    if getattr(user, "status", None) != User.Status.ACTIVE:
        raise AccountDisabled()


def _assert_room_joinable(room: Room) -> None:
    """寝室仍可加入（docs/04 §8 的 ROOM_* 错误码）。"""
    if room.status == Room.Status.ARCHIVED:
        raise RoomArchived(room.code)
    if room.status == Room.Status.DISSOLVED:
        raise RoomDissolved(room.code)
    if room.status == Room.Status.LOCKED:
        raise RoomLocked(room.code)
    if room.status == Room.Status.FULL:
        raise RoomFull(room.code)
    if room.status != Room.Status.RECRUITING:
        raise InvalidState("ROOM_STATUS", "寝室当前不可加入")
    if room.member_count >= room.capacity:
        raise RoomFull(room.code)


def _fetch_participant_request(actor: Any, request_pk: Any) -> ConnectionRequest:
    """无锁读取请求并校验参与者身份；不存在/非参与者统一 404。"""
    try:
        pk = int(request_pk)
    except (TypeError, ValueError):
        raise ConnectionNotFound() from None
    row = (
        ConnectionRequest.objects.select_related(
            "initiator",
            "target",
            "room",
            "room__owner",
        )
        .filter(pk=pk)
        .first()
    )
    if row is None or actor.pk not in (row.initiator_id, row.target_id):
        raise ConnectionNotFound()
    return row


def _relock_request(request_pk: int) -> ConnectionRequest:
    row = (
        ConnectionRequest.objects.select_for_update(of=("self",))
        .select_related("initiator", "target", "room", "room__owner")
        .filter(pk=int(request_pk))
        .first()
    )
    if row is None:
        raise ConnectionNotFound()
    return row


def _own_confirm_at(row: ConnectionRequest, actor: Any) -> datetime | None:
    if actor.pk == row.initiator_id:
        return row.initiator_confirm_at
    return row.target_confirm_at


def _mark_confirmed(row: ConnectionRequest, actor: Any, now: datetime) -> str:
    field = (
        "initiator_confirm_at"
        if actor.pk == row.initiator_id
        else "target_confirm_at"
    )
    setattr(row, field, now)
    return field


def _other_party(row: ConnectionRequest, actor: Any) -> Any:
    return row.target if actor.pk == row.initiator_id else row.initiator


def _joiner(row: ConnectionRequest) -> Any:
    """入寝方：房主邀请时目标入寝，申请时发起人入寝。"""
    return row.target if row.type == ConnectionRequest.Type.INVITE else row.initiator


def _room_payload_keys(row: ConnectionRequest) -> dict[str, Any]:
    if row.room_id is None:
        return {}
    return {"room_code": row.room.code}


def _expire_if_due(
    row: ConnectionRequest,
    now: datetime,
    *,
    request_id: str = "",
) -> bool:
    """锁内懒过期：到期则关闭为 ``EXPIRED/TIMEOUT`` 并返回 ``True``。"""
    if (
        row.status not in OPEN_STATUSES
        or row.expires_at is None
        or row.expires_at > now
    ):
        return False
    previous = row.status
    row.status = ConnectionRequest.Status.EXPIRED
    row.close_reason = ConnectionRequest.CloseReason.TIMEOUT
    row.closed_by = None
    row.version += 1
    row.save(
        update_fields=[
            "status",
            "close_reason",
            "closed_by",
            "version",
            "updated_at",
        ]
    )
    payload: dict[str, Any] = {
        "connection_id": row.pk,
        "reason": ConnectionRequest.CloseReason.TIMEOUT,
    }
    payload.update(_room_payload_keys(row))
    for party in (row.initiator, row.target):
        notify(party, Notification.Type.SYSTEM, payload)
    write_audit(
        "CONNECTION_EXPIRED",
        "connection",
        row.pk,
        actor=None,
        meta={"reason": "TIMEOUT", "from_status": previous},
        request_id=request_id,
    )
    return True


def _assert_confirmable(row: ConnectionRequest) -> None:
    if row.status in OPEN_STATUSES and row.status != ConnectionRequest.Status.PENDING:
        return
    if row.status == ConnectionRequest.Status.PENDING:
        raise InvalidState("NOT_CONTACT_SHARED", "请先等对方接受请求")
    raise RequestClosed()


def _assert_pending(row: ConnectionRequest, *, reason: str = "NOT_PENDING") -> None:
    if row.status == ConnectionRequest.Status.PENDING:
        return
    if row.status in OPEN_STATUSES:
        raise InvalidState(reason, "请求状态已变更，请刷新")
    raise RequestClosed()


# --------------------------------------------------------------------------- #
# 创建请求
# --------------------------------------------------------------------------- #
def _validate_combination(
    type_value: Any,
    room_id: Any,
    capacity_pref: Any,
) -> tuple[str, int | None, int | None]:
    """校验 type/room/capacity 组合，返回规范化后的三元组（docs/04 §4.4）。"""
    request_type = str(getattr(type_value, "value", type_value) or "").strip().upper()
    if request_type not in ConnectionRequest.Type.values:
        raise InvalidType("type 只能是 INVITE 或 APPLY")

    room_pk = None
    if room_id is not None:
        try:
            room_pk = int(room_id)
        except (TypeError, ValueError):
            raise InvalidType("room_id 必须是正整数") from None

    capacity = None
    if capacity_pref is not None and capacity_pref != "":
        try:
            capacity = int(capacity_pref)
        except (TypeError, ValueError):
            raise CapacityInvalid(capacity_pref) from None

    if request_type == ConnectionRequest.Type.APPLY:
        if room_pk is None:
            raise InvalidType("申请入寝必须提供 room_id")
        if capacity is not None:
            raise InvalidType("申请入寝不能提供 capacity_pref")
        return request_type, room_pk, None

    if room_pk is None:
        if capacity is None:
            raise CapacityInvalid(None)
        if capacity not in Room.Capacity.values:
            raise CapacityInvalid(capacity)
        return request_type, None, capacity

    if capacity is not None:
        raise InvalidType("邀请他人入寝不能提供 capacity_pref")
    return request_type, room_pk, None


def _assert_no_open_between(initiator: Any, target: Any) -> None:
    exists = ConnectionRequest.objects.filter(
        Q(initiator=initiator, target=target) | Q(initiator=target, target=initiator),
        status__in=OPEN_STATUSES,
    ).exists()
    if exists:
        raise DuplicateRequest()


def _assert_rate_limits(initiator: Any, now: datetime) -> None:
    in_flight = ConnectionRequest.objects.filter(
        initiator=initiator,
        status__in=OPEN_STATUSES,
    ).count()
    if in_flight >= IN_FLIGHT_LIMIT:
        raise RateLimited("在途请求已达上限（3 条），请先处理")
    daily = ConnectionRequest.objects.filter(
        initiator=initiator,
        created_at__gte=_day_start(now),
    ).count()
    if daily >= DAILY_LIMIT:
        raise RateLimited("今日发起请求已达上限（10 条）")


def _assert_cooldown(initiator: Any, target: Any, now: datetime) -> None:
    since = now - COOLDOWN
    latest = (
        ConnectionRequest.objects.filter(
            status=ConnectionRequest.Status.DECLINED,
            updated_at__gte=since,
        )
        .filter(
            Q(initiator=initiator, target=target)
            | Q(initiator=target, target=initiator)
        )
        .order_by("-updated_at")
        .first()
    )
    if latest is None:
        return
    remaining = int((latest.updated_at + COOLDOWN - now).total_seconds())
    raise Cooldown(retry_after=max(1, remaining))


def _assert_no_room_rejoin(room: Room, user: Any) -> None:
    """同一房间不可二次回流（docs/02 R-13、docs/03 §1.3.4）。

    退出/被移除/归档后，`(room,user)` 仍保留历史 RoomMember 行；这类用户
    对该房间的新 APPLY / 房主 INVITE 必须在创建时即拒绝，不能等到确认阶段。
    """
    exists = RoomMember.objects.filter(room_id=room.pk, user_id=user.pk).exists()
    if exists:
        raise InvalidState(
            "REJOIN_NOT_ALLOWED",
            "你不能重新加入已退出/被移除的寝室",
        )


def _assert_room_scoped_guards(
    row_type: str,
    room: Room,
    initiator: Any,
    target: Any,
) -> None:
    """房主定向邀请 / 申请入寝的额外守卫（docs/02 §3.2.2、R-13）。"""
    membership = RoomMember.objects.filter(
        room_id=room.pk,
        user_id=initiator.pk,
        status=RoomMember.Status.ACTIVE,
    ).first()
    target_membership = RoomMember.objects.filter(
        room_id=room.pk,
        user_id=target.pk,
        status=RoomMember.Status.ACTIVE,
    ).first()

    if row_type == ConnectionRequest.Type.APPLY:
        if target_membership is None or target_membership.role != RoomMember.Role.OWNER:
            raise InvalidTarget("NOT_OWNER", "对方不是该寝室的房主")
        if membership is not None:
            raise InvalidTarget("IS_MEMBER", "你已在该寝室内")
        joiner = initiator
    else:
        if membership is None or membership.role != RoomMember.Role.OWNER:
            raise InvalidTarget("NOT_OWNER", "只有房主可以邀请他人入寝")
        if target_membership is not None:
            raise InvalidTarget("IS_MEMBER", "对方已在该寝室内")
        joiner = target
    _assert_room_joinable(room)
    # 房间可加入后，再按 R-13 拒绝同房历史成员（不得回流）。
    _assert_no_room_rejoin(room, joiner)



def create_request(
    actor: Any,
    *,
    type: Any = None,
    target_uid: Any = None,
    room_id: Any = None,
    capacity_pref: Any = None,
    message: Any = "",
    request_id: str = "",
    at: datetime | None = None,
) -> ConnectionRequest:
    """创建 INVITE / APPLY（docs/02 §3.2、docs/04 §4.4）。"""
    now = _now(at)
    request_type, room_pk, capacity = _validate_combination(
        type, room_id, capacity_pref
    )
    uid = str(target_uid or "").strip()
    body = str(message or "")[:MESSAGE_MAX_LENGTH]

    with transaction.atomic():
        _assert_account_active(actor)
        require_locked_window(actor.college, at=now)
        _assert_self_profile_complete(actor)

        if not uid:
            raise InvalidTarget("TARGET_REQUIRED", "请提供 target_uid")
        if uid == actor.uid:
            raise SelfRequest()
        target = User.objects.filter(uid=uid).first()
        if target is None or getattr(target, "status", None) != User.Status.ACTIVE:
            raise UserNotFound()

        lock_users([actor.pk, target.pk])
        actor = User.objects.get(pk=actor.pk)
        target = User.objects.get(pk=target.pk)
        _assert_account_active(actor)
        if getattr(target, "status", None) != User.Status.ACTIVE:
            raise UserNotFound()

        if actor.college != target.college:
            raise WrongCollege()
        if actor.gender != target.gender:
            raise WrongGender()
        if _is_blocked(actor.pk, target.pk):
            raise Blocked()
        if room_pk is None:
            # 人-人邀请：双方都必须在寝外（X-04/X-05）。
            if _active_membership(actor) is not None:
                raise AlreadyInRoom()
            if _active_membership(target) is not None:
                raise TargetInRoom()
        elif request_type == ConnectionRequest.Type.INVITE:
            # 房主定向邀请：只有被邀请方必须在寝外（房主本人就在该寝）。
            if _active_membership(target) is not None:
                raise TargetInRoom()
        else:
            # 申请入寝：只有申请人必须在寝外（房主本人就在该寝）。
            if _active_membership(actor) is not None:
                raise AlreadyInRoom()
        _assert_target_profile_complete(target)

        lock_requests(_open_request_ids_for([actor.pk, target.pk]))
        room = None
        if room_pk is not None:
            room = lock_room_row(room_pk)
            if room is None:
                raise RoomNotFound()

        _assert_no_open_between(actor, target)
        _assert_rate_limits(actor, now)
        _assert_cooldown(actor, target, now)
        if room is not None:
            _assert_room_scoped_guards(request_type, room, actor, target)

        try:
            with transaction.atomic():
                row = ConnectionRequest.objects.create(
                    type=request_type,
                    initiator=actor,
                    target=target,
                    room=room,
                    status=ConnectionRequest.Status.PENDING,
                    message=body,
                    capacity_pref=capacity,
                    expires_at=now + PENDING_TTL,
                )
        except IntegrityError as exc:
            raise DuplicateRequest() from exc

        payload: dict[str, Any] = {
            "connection_id": row.pk,
            "type": request_type,
            "from_nickname": actor.nickname,
        }
        if room is not None:
            payload["room_code"] = room.code
        notify(target, Notification.Type.CONNECTION_RECEIVED, payload)

        meta: dict[str, Any] = {"type": request_type, "target_id": target.pk}
        if room is not None:
            meta["room_id"] = room.pk
        if capacity is not None:
            meta["capacity_pref"] = capacity
        write_audit(
            "CONNECTION_CREATED",
            "connection",
            row.pk,
            actor=actor,
            meta=meta,
            request_id=request_id,
        )
    return row


# --------------------------------------------------------------------------- #
# accept / decline / cancel
# --------------------------------------------------------------------------- #
def accept_request(
    actor: Any,
    request_pk: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> ConnectionRequest:
    """目标接受请求：``PENDING → CONTACT_SHARED``；发起人已预确认则直接成立（docs/02 §3.3、§3.5.5）。"""
    now = _now(at)
    row = _fetch_participant_request(actor, request_pk)
    if row.target_id != actor.pk:
        raise ActionForbidden("只有被邀请方可以接受请求")

    expired = False
    with transaction.atomic():
        require_locked_window(row.initiator.college, at=now)
        lock_users([row.initiator_id, row.target_id])
        current = _relock_request(row.pk)
        if _expire_if_due(current, now, request_id=request_id):
            expired = True
        else:
            _assert_pending(current)
            initiator, target = current.initiator, current.target
            _assert_account_active(initiator)
            _assert_account_active(target)
            if _is_blocked(initiator.pk, target.pk):
                raise Blocked()
            if initiator.college != target.college:
                raise WrongCollege()
            if initiator.gender != target.gender:
                raise WrongGender()
            _assert_self_profile_complete(initiator)
            _assert_target_profile_complete(target)
            if current.room_id is None:
                if _active_membership(initiator) is not None:
                    raise AlreadyInRoom()
                if _active_membership(target) is not None:
                    raise TargetInRoom()
            else:
                _assert_room_joinable(current.room)
                if _active_membership(_joiner(current)) is not None:
                    raise AlreadyInRoom()

            current.status = ConnectionRequest.Status.CONTACT_SHARED
            current.contact_shared_at = now
            current.expires_at = now + CONTACT_TTL
            current.version += 1
            current.save(
                update_fields=[
                    "status",
                    "contact_shared_at",
                    "expires_at",
                    "version",
                    "updated_at",
                ]
            )
            notify(
                initiator,
                Notification.Type.CONTACT_SHARED,
                {"connection_id": current.pk},
            )
            write_audit(
                "CONNECTION_ACCEPTED",
                "connection",
                current.pk,
                actor=target,
                meta={"from": "PENDING", "to": "CONTACT_SHARED"},
                request_id=request_id,
            )
    if expired:
        raise RequestExpired()
    if (
        current.status == ConnectionRequest.Status.CONTACT_SHARED
        and current.initiator_confirm_at is not None
    ):
        # 发起人已预先确认：被邀请方点“同意”就等于双方都确认，直接成立组寝。
        return confirm_request(actor, current.pk, request_id=request_id, at=at)[1]
    return current


def decline_request(
    actor: Any,
    request_pk: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> ConnectionRequest:
    """目标拒绝请求：``PENDING → DECLINED``（docs/02 §3.4.1）。"""
    now = _now(at)
    row = _fetch_participant_request(actor, request_pk)
    if row.target_id != actor.pk:
        raise ActionForbidden("只有被邀请方可以拒绝请求")

    expired = False
    with transaction.atomic():
        require_locked_window(row.initiator.college, at=now)
        lock_users([row.initiator_id, row.target_id])
        current = _relock_request(row.pk)
        if _expire_if_due(current, now, request_id=request_id):
            expired = True
        else:
            _assert_pending(current)
            current.status = ConnectionRequest.Status.DECLINED
            current.close_reason = ConnectionRequest.CloseReason.DECLINED
            current.closed_by = current.target
            current.version += 1
            current.save(
                update_fields=[
                    "status",
                    "close_reason",
                    "closed_by",
                    "version",
                    "updated_at",
                ]
            )
            payload: dict[str, Any] = {"connection_id": current.pk}
            payload.update(_room_payload_keys(current))
            notify(current.initiator, Notification.Type.DECLINED, payload)
            write_audit(
                "CONNECTION_DECLINED",
                "connection",
                current.pk,
                actor=current.target,
                meta={"reason": "DECLINED"},
                request_id=request_id,
            )
    if expired:
        raise RequestExpired()
    return current


def cancel_request(
    actor: Any,
    request_pk: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> ConnectionRequest:
    """撤回/结束了解：``PENDING`` 仅发起人，其余在途任一方（docs/02 §3.4.2）。"""
    now = _now(at)
    row = _fetch_participant_request(actor, request_pk)

    expired = False
    with transaction.atomic():
        # 撤回不受时间窗限制：只按锁序锁窗，不校验开放（docs/02 §11.3）。
        lock_window(row.initiator.college)
        lock_users([row.initiator_id, row.target_id])
        current = _relock_request(row.pk)
        if _expire_if_due(current, now, request_id=request_id):
            expired = True
        else:
            if current.status == ConnectionRequest.Status.PENDING:
                if actor.pk != current.initiator_id:
                    raise ActionForbidden("待处理阶段只有发起人可以撤回")
                reason = ConnectionRequest.CloseReason.INITIATOR_CANCEL
            elif current.status in (
                ConnectionRequest.Status.CONTACT_SHARED,
                ConnectionRequest.Status.CONFIRMING,
            ):
                reason = ConnectionRequest.CloseReason.END_UNDERSTANDING
            else:
                raise RequestClosed()

            other = _other_party(current, actor)
            current.status = ConnectionRequest.Status.CANCELLED
            current.close_reason = reason
            current.closed_by = actor
            current.version += 1
            current.save(
                update_fields=[
                    "status",
                    "close_reason",
                    "closed_by",
                    "version",
                    "updated_at",
                ]
            )
            payload: dict[str, Any] = {
                "connection_id": current.pk,
                "reason": str(reason),
            }
            payload.update(_room_payload_keys(current))
            notify(other, Notification.Type.SYSTEM, payload)
            write_audit(
                "CONNECTION_CANCELLED",
                "connection",
                current.pk,
                actor=actor,
                meta={"reason": str(reason)},
                request_id=request_id,
            )
    if expired:
        raise RequestExpired()
    return current


# --------------------------------------------------------------------------- #
# pre-approve（发起人先确认）
# --------------------------------------------------------------------------- #
def pre_approve_request(
    actor: Any,
    request_pk: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> ConnectionRequest:
    """发起人在 ``PENDING`` 阶段先确认，对方同意时点一次即可成立（docs/02 §3.5.5）。

    只写 ``initiator_confirm_at``，状态仍是 ``PENDING``：对方上线后点“同意”
    就同时补齐自己的确认，直接进入 ``CONFIRMED``。幂等，重复调用不重复审计。
    """
    now = _now(at)
    row = _fetch_participant_request(actor, request_pk)
    if row.initiator_id != actor.pk:
        raise ActionForbidden("只有发起人可以预先确认")

    expired = False
    with transaction.atomic():
        require_locked_window(row.initiator.college, at=now)
        lock_users([row.initiator_id, row.target_id])
        current = _relock_request(row.pk)
        if _expire_if_due(current, now, request_id=request_id):
            expired = True
        else:
            _assert_pending(current)
            _assert_account_active(current.initiator)
            _assert_account_active(current.target)
            if _is_blocked(current.initiator_id, current.target_id):
                raise Blocked()
            if current.initiator_confirm_at is None:
                current.initiator_confirm_at = now
                current.version += 1
                current.save(
                    update_fields=[
                        "initiator_confirm_at",
                        "version",
                        "updated_at",
                    ]
                )
                write_audit(
                    "CONNECTION_PRE_APPROVED",
                    "connection",
                    current.pk,
                    actor=actor,
                    meta={"status": str(current.status)},
                    request_id=request_id,
                )
    if expired:
        raise RequestExpired()
    return current


# --------------------------------------------------------------------------- #
# confirm（两步）
# --------------------------------------------------------------------------- #
def _close_other_open_requests(
    locked: dict[int, ConnectionRequest],
    current: ConnectionRequest,
    room: Room | None,
    *,
    request_id: str = "",
) -> int:
    """成立后关闭双方其余在途请求（docs/02 §3.5.4）。"""
    closed = 0
    for other in locked.values():
        if other.pk == current.pk:
            continue
        if other.status not in OPEN_STATUSES:
            continue
        other.status = ConnectionRequest.Status.CANCELLED
        other.close_reason = ConnectionRequest.CloseReason.AUTO_CANCELLED
        other.closed_by = None
        other.version += 1
        other.save(
            update_fields=[
                "status",
                "close_reason",
                "closed_by",
                "version",
                "updated_at",
            ]
        )
        payload: dict[str, Any] = {
            "connection_id": other.pk,
            "reason": "AUTO_CANCELLED",
        }
        if room is not None:
            payload["room_code"] = room.code
        for party in (other.initiator, other.target):
            notify(party, Notification.Type.SYSTEM, payload)
        meta: dict[str, Any] = {"reason": "AUTO_CANCELLED"}
        if other.room_id is not None:
            meta["room_id"] = other.room_id
        elif room is not None:
            meta["room_id"] = room.pk
        write_audit(
            "CONNECTION_AUTO_CANCELLED",
            "connection",
            other.pk,
            actor=None,
            meta=meta,
            request_id=request_id,
        )
        closed += 1
    return closed


def _establish_room(
    current: ConnectionRequest,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> Room:
    """按类型成立组寝：人-人建寝，寝室邀请/申请入寝（docs/02 §3.5.4）。"""
    if current.room_id is None:
        return room_services.create_room_for_pair(
            current.initiator,
            current.target,
            current.capacity_pref,
            connection=current,
            request_id=request_id,
            at=at,
        )

    room = current.room
    joiner = _joiner(current)
    room_services.join_room_for_confirm(
        room,
        joiner,
        current,
        request_id=request_id,
        at=at,
    )
    # 入寝在 rooms 服务里对另一份 Room 实例加锁并写库；刷新本地快照，
    # 保证 confirm 响应里的 member_count/status 与 GET / DB 一致。
    room.refresh_from_db(fields=["member_count", "status"])
    # 入寝路径由 rooms 服务负责成员通知；CONFIRMED 由这里补发（docs/02 §3.5.5）。
    payload: dict[str, Any] = {
        "connection_id": current.pk,
        "room_code": room.code,
        "room_title": room.title,
    }
    for party in (current.initiator, current.target):
        notify(party, Notification.Type.CONFIRMED, payload)
    return room


def confirm_request(
    actor: Any,
    request_pk: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> tuple[str, ConnectionRequest, Room | None]:
    """二次确认（docs/02 §3.5）；返回 ``(status, request, room)``。"""
    now = _now(at)
    row = _fetch_participant_request(actor, request_pk)

    expired = False
    outcome = "CONFIRMING"
    room: Room | None = None
    with transaction.atomic():
        require_locked_window(row.initiator.college, at=now)
        user_ids = [row.initiator_id, row.target_id]
        lock_users(user_ids)
        request_ids = _open_request_ids_for(user_ids)
        if row.room_id is not None:
            request_ids = sorted(
                set(request_ids) | set(_open_request_ids_for_room(row.room_id))
            )
        locked = {item.pk: item for item in lock_requests(request_ids)}
        current = locked.get(row.pk)
        if current is None:
            current = _relock_request(row.pk)
            locked[current.pk] = current
        if current.room_id is not None:
            locked_room = lock_room_row(current.room_id)
            if locked_room is None:
                raise RoomNotFound()
            current.room = locked_room

        if _expire_if_due(current, now, request_id=request_id):
            expired = True
        else:
            _assert_confirmable(current)
            if _own_confirm_at(current, actor) is not None:
                raise AlreadyConfirmed()
            initiator, target = current.initiator, current.target
            _assert_account_active(initiator)
            _assert_account_active(target)
            if _is_blocked(initiator.pk, target.pk):
                raise Blocked()
            if initiator.college != target.college:
                raise WrongCollege()
            if initiator.gender != target.gender:
                raise WrongGender()
            _assert_self_profile_complete(initiator)
            _assert_target_profile_complete(target)
            if current.room_id is None:
                if _active_membership(initiator) is not None:
                    raise AlreadyInRoom()
                if _active_membership(target) is not None:
                    raise TargetInRoom()
            else:
                _assert_room_joinable(current.room)
                joiner = _joiner(current)
                if _active_membership(joiner) is not None:
                    raise AlreadyInRoom()
                if current.room.gender != joiner.gender:
                    raise WrongGender()
                if current.room.college != joiner.college:
                    raise WrongCollege()
            if current.type == ConnectionRequest.Type.INVITE:
                if current.room_id is not None and current.capacity_pref is not None:
                    raise InvalidType("请求数据异常，请重新发起")
            elif current.room_id is None:
                raise InvalidType("请求数据异常，请重新发起")

            other_confirmed_at = (
                current.target_confirm_at
                if actor.pk == current.initiator_id
                else current.initiator_confirm_at
            )
            # 对方已预先确认（pre-approve）时，本次确认不必再等对方上线，
            # 直接走成立分支（docs/02 §3.5.5）。
            if (
                current.status == ConnectionRequest.Status.CONTACT_SHARED
                and other_confirmed_at is None
            ):
                own_field = _mark_confirmed(current, actor, now)
                current.status = ConnectionRequest.Status.CONFIRMING
                current.expires_at = now + CONFIRM_TTL
                current.version += 1
                current.save(
                    update_fields=[
                        own_field,
                        "status",
                        "expires_at",
                        "version",
                        "updated_at",
                    ]
                )
                notify(
                    _other_party(current, actor),
                    Notification.Type.CONFIRM_PENDING,
                    {"connection_id": current.pk},
                )
                write_audit(
                    "CONNECTION_CONFIRMED_STEP1",
                    "connection",
                    current.pk,
                    actor=actor,
                    meta={
                        "to": "CONFIRMING",
                        "expires_at": isoformat(current.expires_at),
                    },
                    request_id=request_id,
                )
                outcome = "CONFIRMING"
            else:
                has_room = current.room_id is not None
                own_field = _mark_confirmed(current, actor, now)
                room = _establish_room(current, request_id=request_id, at=now)
                current.room = room
                # 人-人 INVITE 建寝后 room 非空，必须清空 capacity_pref
                # 以满足 ck_conn_capacity_scope（room 与 capacity_pref 互斥）。
                update_fields = [
                    own_field,
                    "room",
                    "status",
                    "close_reason",
                    "expires_at",
                    "version",
                    "updated_at",
                ]
                if not has_room:
                    current.capacity_pref = None
                    update_fields.append("capacity_pref")
                current.status = ConnectionRequest.Status.CONFIRMED
                current.close_reason = ""
                # CONFIRMED 为终态，不再有过期时间（docs/seed-spec §2.6）。
                current.expires_at = None
                current.version += 1
                current.save(update_fields=update_fields)
                _close_other_open_requests(
                    locked,
                    current,
                    room,
                    request_id=request_id,
                )
                write_audit(
                    "CONNECTION_CONFIRMED",
                    "connection",
                    current.pk,
                    actor=actor,
                    meta={
                        "room_id": room.pk,
                        "room_code": room.code,
                        "type": current.type,
                    },
                    request_id=request_id,
                )
                outcome = "CONFIRMED"
    if expired:
        raise RequestExpired()
    return outcome, current, room


# --------------------------------------------------------------------------- #
# 查询 & 过期清理
# --------------------------------------------------------------------------- #
def normalize_box(value: Any) -> str:
    """``inbox|incoming|received`` → inbox；``sent|outgoing|...`` → sent。"""
    raw = str(value or "").strip().lower()
    if raw in _SENT_ALIASES:
        return "sent"
    return "inbox"


def list_requests(
    actor: Any,
    *,
    box: Any = "inbox",
    statuses: list[str] | None = None,
) -> Any:
    """参与者的请求列表（按 ``updated_at DESC, id DESC``，docs/04 §4.4）。"""
    queryset = ConnectionRequest.objects.select_related(
        "initiator",
        "target",
        "room",
        "room__owner",
        "closed_by",
    )
    if normalize_box(box) == "sent":
        queryset = queryset.filter(initiator=actor)
    else:
        queryset = queryset.filter(target=actor)
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    return queryset.order_by("-updated_at", "-id")


def get_request(actor: Any, request_pk: Any) -> ConnectionRequest:
    """详情：仅参与者可见，否则 404 CONNECTION_NOT_FOUND。"""
    return _fetch_participant_request(actor, request_pk)


def expire_due_connections(
    now: datetime | None = None,
    *,
    limit: int = 500,
    request_id: str = "",
) -> int:
    """cron：把到期的在途请求关闭为 ``EXPIRED/TIMEOUT``（docs/02 §3.6）。"""
    moment = _now(now)
    ids = list(
        ConnectionRequest.objects.filter(
            status__in=OPEN_STATUSES,
            expires_at__lte=moment,
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )
    count = 0
    for pk in ids:
        with transaction.atomic():
            row = (
                ConnectionRequest.objects.select_for_update(of=("self",))
                .select_related("initiator", "target", "room")
                .filter(pk=pk)
                .first()
            )
            if row is None:
                continue
            if _expire_if_due(row, moment, request_id=request_id):
                count += 1
    return count
