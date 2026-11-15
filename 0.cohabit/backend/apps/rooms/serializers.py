"""rooms 输出结构（docs/04 §3.6–§3.8）与输入校验。

输出统一用普通 ``dict``，时间字段经 :func:`apps.rooms.utils.isoformat` 转成
UTC ISO8601（``...Z``）字符串，避免 DRF 直接序列化 datetime 带本地时区偏移。
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Room, RoomMember, RoomTransfer
from .utils import TITLE_MAX_LENGTH, isoformat

MEMBER_PREVIEW_LIMIT = 6


def user_summary(user: Any) -> dict[str, Any]:
    """UserSummary：uid/nickname/avatar_key/gender/college/major/grade。"""
    return UserSummarySerializer(user).data


def _dt(value: Any) -> str | None:
    return isoformat(value) if value is not None else None


def _room_members(room: Room) -> list[RoomMember]:
    """该房间全部 RoomMember 记录（按加入时间），优先用预取缓存。"""
    cached = getattr(room, "_prefetched_objects_cache", {}).get("members")
    rows = (
        list(cached)
        if cached is not None
        else list(
            RoomMember.objects.filter(room_id=room.pk).select_related("user")
        )
    )
    rows.sort(key=lambda row: (row.created_at, row.pk))
    return rows


def _active_members(room: Room) -> list[RoomMember]:
    """ACTIVE 成员（按加入时间）。"""
    return [
        row for row in _room_members(room) if row.status == RoomMember.Status.ACTIVE
    ]


def _detail_members(room: Room) -> list[RoomMember]:
    """RoomDetail.members：终态返回最终名单，其余仅 ACTIVE（docs/04 §3.7）。"""
    if room.status in (Room.Status.ARCHIVED, Room.Status.DISSOLVED):
        return _room_members(room)
    return _active_members(room)


def member_payload(member: RoomMember) -> dict[str, Any]:
    """RoomDetail.members 元素：uid/nickname/avatar_key/role/status/created_at。"""
    return {
        "uid": member.user.uid,
        "nickname": member.user.nickname,
        "avatar_key": user_summary(member.user)["avatar_key"],
        "role": member.role,
        "status": member.status,
        "created_at": _dt(member.created_at),
    }


def room_summary(
    room: Room,
    viewer: Any = None,
    *,
    membership: RoomMember | None = None,
    pending_transfer: RoomTransfer | None = None,
) -> dict[str, Any]:
    """RoomSummary（docs/04 §3.6）。不含 contact/email。"""
    members = _active_members(room)
    owner = room.owner
    my_role = membership.role if membership is not None else None
    payload: dict[str, Any] = {
        "id": room.pk,
        "code": room.code,
        "title": room.title,
        "capacity": room.capacity,
        "member_count": room.member_count,
        "status": room.status,
        "gender": room.gender,
        "college": room.college,
        "major": room.major,
        "tags": list(room.tags or []),
        "owner": user_summary(owner),
        "member_preview": [
            user_summary(member.user) for member in members[:MEMBER_PREVIEW_LIMIT]
        ],
        "can_apply": _can_apply(room, viewer, membership),
        "my_role": my_role,
        "pending_transfer": (
            transfer_summary(pending_transfer) if pending_transfer is not None else None
        ),
    }
    return payload


def _can_apply(
    room: Room,
    viewer: Any,
    membership: RoomMember | None,
) -> bool:
    """本人能否申请入寝（与 profiles.me_context._can_apply 口径一致）。"""
    if viewer is None or getattr(viewer, "pk", None) is None:
        return False
    if room.status != Room.Status.RECRUITING:
        return False
    if room.member_count >= room.capacity:
        return False
    if getattr(viewer, "gender", None) != room.gender:
        return False
    if getattr(viewer, "college", None) != room.college:
        return False
    if membership is not None and membership.status == RoomMember.Status.ACTIVE:
        return False
    from apps.connections.models import OPEN_STATUSES, ConnectionRequest

    if RoomMember.objects.filter(
        user_id=viewer.pk,
        status=RoomMember.Status.ACTIVE,
    ).exists():
        return False
    return not ConnectionRequest.objects.filter(
        initiator_id=viewer.pk,
        room_id=room.pk,
        status__in=OPEN_STATUSES,
    ).exists()


def room_actions(room: Room, viewer: Any, membership: RoomMember | None) -> dict[str, bool]:
    """RoomDetail.actions（docs/04 §3.7 + §5.2 权限矩阵）。"""
    is_owner = viewer is not None and room.owner_id == viewer.pk
    is_active_member = membership is not None and membership.status == RoomMember.Status.ACTIVE
    open_status = room.status in (
        Room.Status.RECRUITING,
        Room.Status.FULL,
        Room.Status.LOCKED,
    )
    return {
        "can_lock": bool(is_owner and room.status == Room.Status.RECRUITING),
        "can_unlock": bool(is_owner and room.status == Room.Status.LOCKED),
        "can_dissolve": bool(is_owner and open_status),
        "can_leave": bool(
            is_active_member
            and not is_owner
            and membership is not None
            and membership.role == RoomMember.Role.MEMBER
            and open_status
        ),
        "can_remove": bool(is_owner and open_status),
        "can_transfer": bool(is_owner and open_status and room.member_count >= 2),
        "can_edit": bool(is_owner and open_status),
    }


def room_detail(
    room: Room,
    viewer: Any = None,
    *,
    membership: RoomMember | None = None,
    pending_transfer: RoomTransfer | None = None,
) -> dict[str, Any]:
    """RoomDetail（docs/04 §3.7）：RoomSummary + members/actions/时间字段。"""
    payload = room_summary(
        room,
        viewer,
        membership=membership,
        pending_transfer=pending_transfer,
    )
    payload["members"] = [member_payload(member) for member in _detail_members(room)]
    payload["actions"] = room_actions(room, viewer, membership)
    payload["created_at"] = _dt(room.created_at)
    payload["archived_at"] = _dt(room.archived_at)
    payload["dissolved_at"] = _dt(room.dissolved_at)
    return payload


def transfer_summary(transfer: RoomTransfer) -> dict[str, Any]:
    """RoomTransferSummary（docs/04 §3.8）。"""
    return {
        "id": transfer.pk,
        "status": transfer.status,
        "from_owner": user_summary(transfer.from_owner),
        "to_member": user_summary(transfer.to_member),
        "expires_at": _dt(transfer.expires_at),
        "created_at": _dt(transfer.created_at),
    }


def public_room_payload(room: Room) -> dict[str, Any]:
    """公开房间页（docs/04 §4.3）：不含 uid/contact/owner 对象。

    ``id`` 为内部主键（docs/04 §3.6），前端跳转/动作复用；不含任何联系方式。
    """
    members = _active_members(room)
    return {
        "id": room.pk,
        "code": room.code,
        "title": room.title,
        "capacity": room.capacity,
        "member_count": room.member_count,
        "status": room.status,
        "college": room.college,
        "tags": list(room.tags or []),
        "members": [
            {
                "nickname": member.user.nickname,
                "avatar_key": user_summary(member.user)["avatar_key"],
            }
            for member in members
        ],
    }


def pending_application_payload(request: Any) -> dict[str, Any]:
    """``/api/rooms/mine`` 的 pending_applications 元素（不含 contact）。"""
    return {
        "id": request.pk,
        "type": request.type,
        "status": request.status,
        "initiator": user_summary(request.initiator),
        "message": request.message,
        "expires_at": _dt(request.expires_at),
    }


# --------------------------------------------------------------------------- #
# 输入校验
# --------------------------------------------------------------------------- #
class RoomUpdateSerializer(serializers.Serializer):
    """PATCH /api/rooms/:id 的 body：title/tags 都可选，至少给一个。"""

    title = serializers.CharField(
        max_length=TITLE_MAX_LENGTH,
        required=False,
        allow_blank=False,
        allow_null=False,
        trim_whitespace=True,
        error_messages={
            "blank": "标题不能为空",
            "max_length": f"标题最长 {TITLE_MAX_LENGTH} 字",
            "null": "标题不能为空",
        },
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=20, allow_blank=False),
        required=False,
        max_length=8,
        allow_empty=True,
        error_messages={
            "max_length": "标签最多 8 个",
            "not_a_list": "tags 必须是字符串数组",
        },
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError(
                {"detail": "至少提供 title 或 tags 中的一个字段"}
            )
        return attrs


class TransferCreateSerializer(serializers.Serializer):
    """POST /api/rooms/:id/transfer 的 body：``{"to_uid": "..."}``。"""

    to_uid = serializers.CharField(
        max_length=10,
        allow_blank=False,
        error_messages={
            "blank": "to_uid 不能为空",
            "required": "to_uid 必填",
            "max_length": "to_uid 不合法",
        },
    )
