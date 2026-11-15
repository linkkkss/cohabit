"""房主转让服务（docs/02 §6）。

一笔寝室同时最多一条 PENDING 转让（数据库 ``uq_room_pending_transfer`` 兜底）。
锁顺序沿用 docs/02 §11.2：窗口 → 用户 → 房间 → 转让 → 成员。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.audit import write_audit
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .exceptions import (
    ActionForbidden,
    InvalidState,
    InvalidTarget,
    NotOwner,
    RoomArchived,
    RoomDissolved,
    RoomNotFound,
    TransferExists,
    TransferExpired,
    TransferNotFound,
)
from .locking import (
    lock_members,
    lock_requests,
    lock_room_row,
    lock_transfer,
    lock_users,
    open_request_ids,
    require_locked_window,
)
from .models import Room, RoomMember, RoomTransfer
from .services import OPEN_ROOM_STATUSES, TRANSFER_TTL
from .utils import isoformat


def _resolve_user(identifier: Any) -> User | None:
    """目标用户既接受 UID（10 位字符串）也接受主键（测试/内部调用）。"""
    if isinstance(identifier, User):
        return identifier
    if identifier is None:
        return None
    text = str(identifier).strip()
    if not text:
        return None
    if text.isdigit() and len(text) == 10:
        return User.objects.filter(uid=text).first()
    if text.isdigit():
        return User.objects.filter(pk=int(text)).first()
    return None


def _assert_room_usable(room: Room) -> None:
    if room.status == Room.Status.DISSOLVED:
        raise RoomDissolved(room.code)
    if room.status == Room.Status.ARCHIVED:
        raise RoomArchived(room.code)
    if room.status not in OPEN_ROOM_STATUSES:
        raise InvalidState("ROOM_TERMINAL")


def _transfer_payload(room: Room, transfer: RoomTransfer) -> dict[str, Any]:
    return {"room_code": room.code, "transfer_id": transfer.pk}


def create_transfer(
    actor: User,
    room_id: Any,
    to_user_id: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> RoomTransfer:
    """房主发起转让：目标必须是本寝 ACTIVE 非房主成员（docs/02 §6.2）。"""
    now = at or timezone.now()
    room_pk = getattr(room_id, "pk", room_id)

    with transaction.atomic():
        room = Room.objects.select_related("owner").filter(pk=room_pk).first()
        if room is None:
            raise RoomNotFound()
        require_locked_window(room.college, at=now)
        target = _resolve_user(to_user_id)
        lock_users([actor.pk, room.owner_id])
        if target is None:
            raise InvalidTarget("USER_NOT_FOUND", "目标用户不存在")
        lock_users([target.pk])
        if target.pk == actor.pk:
            raise InvalidTarget("SELF_TRANSFER", "不能转让给自己")

        locked_room = lock_room_row(room.pk)
        if locked_room is None:
            raise RoomNotFound()
        if locked_room.owner_id != actor.pk:
            raise NotOwner()
        _assert_room_usable(locked_room)
        if RoomTransfer.objects.filter(
            room_id=locked_room.pk,
            status=RoomTransfer.Status.PENDING,
        ).exists():
            raise TransferExists()

        members = lock_members(locked_room.pk, [target.pk])
        target_member = next(
            (
                member
                for member in members
                if member.user_id == target.pk
                and member.status == RoomMember.Status.ACTIVE
            ),
            None,
        )
        if target_member is None:
            raise InvalidTarget("NOT_MEMBER", "对方不是本寝成员")
        if target_member.role == RoomMember.Role.OWNER:
            raise InvalidTarget("IS_OWNER", "对方已经是房主")

        expires_at = now + TRANSFER_TTL
        try:
            with transaction.atomic():
                transfer = RoomTransfer.objects.create(
                    room=locked_room,
                    from_owner=actor,
                    to_member=target,
                    status=RoomTransfer.Status.PENDING,
                    expires_at=expires_at,
                )
        except IntegrityError:
            raise TransferExists() from None

        notify(
            target,
            Notification.Type.TRANSFER_RECEIVED,
            {
                "room_code": locked_room.code,
                "transfer_id": transfer.pk,
                "from_nickname": actor.nickname,
                "expires_at": isoformat(expires_at),
            },
        )
        write_audit(
            "TRANSFER_CREATED",
            "transfer",
            transfer.pk,
            actor=actor,
            meta={
                "room_id": locked_room.pk,
                "to_member_id": target.pk,
                "expires_at": isoformat(expires_at),
            },
            request_id=request_id,
        )
        return transfer


def accept_transfer(
    actor: User,
    transfer_id: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> RoomTransfer:
    """被转让成员接受：降级旧房主 → 升级新成员 → 更新 room.owner（docs/02 §6.3）。"""
    now = at or timezone.now()
    transfer_pk = getattr(transfer_id, "pk", transfer_id)

    with transaction.atomic():
        transfer0 = RoomTransfer.objects.filter(pk=transfer_pk).first()
        if transfer0 is None:
            raise TransferNotFound()
        room0 = Room.objects.filter(pk=transfer0.room_id).first()
        if room0 is None:
            raise TransferNotFound()

        require_locked_window(room0.college, at=now)
        lock_users([actor.pk, transfer0.from_owner_id, transfer0.to_member_id])
        lock_requests(open_request_ids(room0))
        locked_room = lock_room_row(room0.pk)
        transfer = lock_transfer(transfer0.pk)
        if transfer is None or locked_room is None:
            raise TransferNotFound()
        if transfer.to_member_id != actor.pk:
            raise ActionForbidden("只有被转让的成员可以接受")
        if transfer.status != RoomTransfer.Status.PENDING:
            raise InvalidState("TRANSFER_NOT_PENDING")
        if transfer.expires_at <= now:
            raise TransferExpired()
        _assert_room_usable(locked_room)
        if locked_room.owner_id != transfer.from_owner_id:
            raise InvalidState("OWNER_CHANGED")

        members = lock_members(
            locked_room.pk,
            [transfer.from_owner_id, transfer.to_member_id],
        )
        by_user = {member.user_id: member for member in members}
        old_owner = by_user.get(transfer.from_owner_id)
        new_owner = by_user.get(transfer.to_member_id)
        if (
            old_owner is None
            or old_owner.status != RoomMember.Status.ACTIVE
            or new_owner is None
            or new_owner.status != RoomMember.Status.ACTIVE
        ):
            raise InvalidState("MEMBER_LEFT")
        if new_owner.role == RoomMember.Role.OWNER:
            raise InvalidState("ALREADY_OWNER")

        # 先降级再升级，避免瞬间出现两个 ACTIVE OWNER 撞唯一约束。
        old_owner.role = RoomMember.Role.MEMBER
        old_owner.save(update_fields=["role", "updated_at"])
        new_owner.role = RoomMember.Role.OWNER
        new_owner.save(update_fields=["role", "updated_at"])
        locked_room.owner_id = new_owner.user_id
        locked_room.save(update_fields=["owner", "updated_at"])

        transfer.status = RoomTransfer.Status.ACCEPTED
        transfer.decided_at = now
        transfer.save(update_fields=["status", "decided_at", "updated_at"])

        payload = _transfer_payload(locked_room, transfer)
        notify(transfer.from_owner, Notification.Type.TRANSFER_ACCEPTED, payload)
        notify(transfer.to_member, Notification.Type.TRANSFER_ACCEPTED, payload)
        write_audit(
            "TRANSFER_ACCEPTED",
            "transfer",
            transfer.pk,
            actor=actor,
            meta={
                "room_id": locked_room.pk,
                "from_owner_id": transfer.from_owner_id,
                "to_member_id": transfer.to_member_id,
            },
            request_id=request_id,
        )
        return transfer


def decline_transfer(
    actor: User,
    transfer_id: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> RoomTransfer:
    """被转让成员拒绝（docs/02 §6.3；不校验窗口）。"""
    now = at or timezone.now()
    transfer_pk = getattr(transfer_id, "pk", transfer_id)

    with transaction.atomic():
        transfer0 = RoomTransfer.objects.filter(pk=transfer_pk).first()
        if transfer0 is None:
            raise TransferNotFound()
        lock_users([actor.pk, transfer0.from_owner_id, transfer0.to_member_id])
        transfer = lock_transfer(transfer0.pk)
        if transfer is None:
            raise TransferNotFound()
        if transfer.to_member_id != actor.pk:
            raise ActionForbidden("只有被转让的成员可以拒绝")
        if transfer.status != RoomTransfer.Status.PENDING:
            raise InvalidState("TRANSFER_NOT_PENDING")
        if transfer.expires_at <= now:
            raise TransferExpired()

        transfer.status = RoomTransfer.Status.DECLINED
        transfer.decided_at = now
        transfer.save(update_fields=["status", "decided_at", "updated_at"])

        room = Room.objects.filter(pk=transfer.room_id).first()
        room_code = room.code if room is not None else ""
        notify(
            transfer.from_owner,
            Notification.Type.TRANSFER_DECLINED,
            {"room_code": room_code, "transfer_id": transfer.pk},
        )
        write_audit(
            "TRANSFER_DECLINED",
            "transfer",
            transfer.pk,
            actor=actor,
            meta={"room_id": transfer.room_id},
            request_id=request_id,
        )
        return transfer


def cancel_transfer(
    actor: User,
    transfer_id: Any,
    *,
    request_id: str = "",
    at: datetime | None = None,
) -> RoomTransfer:
    """原房主撤回转让（docs/02 §6.3；不校验窗口）。"""
    now = at or timezone.now()
    transfer_pk = getattr(transfer_id, "pk", transfer_id)

    with transaction.atomic():
        transfer0 = RoomTransfer.objects.filter(pk=transfer_pk).first()
        if transfer0 is None:
            raise TransferNotFound()
        lock_users([actor.pk, transfer0.from_owner_id])
        transfer = lock_transfer(transfer0.pk)
        if transfer is None:
            raise TransferNotFound()
        if transfer.from_owner_id != actor.pk:
            raise ActionForbidden("只有原房主可以撤回转让")
        if transfer.status != RoomTransfer.Status.PENDING:
            raise InvalidState("TRANSFER_NOT_PENDING")

        transfer.status = RoomTransfer.Status.CANCELLED
        transfer.decided_at = now
        transfer.save(update_fields=["status", "decided_at", "updated_at"])

        room = Room.objects.filter(pk=transfer.room_id).first()
        room_code = room.code if room is not None else ""
        notify(
            transfer.to_member,
            Notification.Type.TRANSFER_CANCELLED,
            {
                "room_code": room_code,
                "transfer_id": transfer.pk,
                "reason": "INITIATOR_CANCEL",
            },
        )
        write_audit(
            "TRANSFER_CANCELLED",
            "transfer",
            transfer.pk,
            actor=actor,
            meta={
                "room_id": transfer.room_id,
                "reason": "INITIATOR_CANCEL",
            },
            request_id=request_id,
        )
        return transfer


def cancel_pending_transfer_for_room(
    room: Room,
    reason: str,
    *,
    actor: User | None = None,
    request_id: str = "",
    at: datetime | None = None,
) -> RoomTransfer | None:
    """寝室解散/归档时取消 PENDING 转让（docs/02 §6.4）。"""
    room_pk = getattr(room, "pk", room)
    with transaction.atomic():
        pending = (
            RoomTransfer.objects.select_for_update()
            .select_related("room", "from_owner", "to_member")
            .filter(room_id=room_pk, status=RoomTransfer.Status.PENDING)
            .first()
        )
        if pending is None:
            return None
        pending.status = RoomTransfer.Status.CANCELLED
        pending.decided_at = at or timezone.now()
        pending.save(update_fields=["status", "decided_at", "updated_at"])
        room_obj = pending.room
        payload = {
            "room_code": room_obj.code,
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
            meta={"room_id": room_obj.pk, "reason": reason},
            request_id=request_id,
        )
        return pending


def expire_due_transfers(
    now: datetime | None = None,
    limit: int = 500,
    *,
    request_id: str = "",
) -> int:
    """把过期 PENDING 转让置为 EXPIRED 并通知双方（cron 调用）。"""
    moment = now or timezone.now()
    due_ids = list(
        RoomTransfer.objects.filter(
            status=RoomTransfer.Status.PENDING,
            expires_at__lte=moment,
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )
    expired = 0
    for transfer_pk in due_ids:
        with transaction.atomic():
            transfer = lock_transfer(transfer_pk)
            if (
                transfer is None
                or transfer.status != RoomTransfer.Status.PENDING
                or transfer.expires_at > moment
            ):
                continue
            transfer.status = RoomTransfer.Status.EXPIRED
            transfer.decided_at = moment
            transfer.save(update_fields=["status", "decided_at", "updated_at"])
            room = Room.objects.filter(pk=transfer.room_id).first()
            room_code = room.code if room is not None else ""
            payload = {"room_code": room_code, "transfer_id": transfer.pk}
            for participant in (transfer.from_owner, transfer.to_member):
                notify(participant, Notification.Type.TRANSFER_EXPIRED, payload)
            write_audit(
                "TRANSFER_EXPIRED",
                "transfer",
                transfer.pk,
                meta={"room_id": transfer.room_id},
                request_id=request_id,
            )
            expired += 1
    return expired


def pending_transfer_for(room: Room) -> RoomTransfer | None:
    """只读查询：该寝当前 PENDING 转让。"""
    if room is None or getattr(room, "pk", None) is None:
        return None
    return (
        RoomTransfer.objects.select_related("from_owner", "to_member")
        .filter(room_id=room.pk, status=RoomTransfer.Status.PENDING)
        .first()
    )
