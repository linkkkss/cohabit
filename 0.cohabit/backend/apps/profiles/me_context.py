"""``/api/me`` 的聚合真值（B6）。

accounts 的 ``MeSerializer`` 只读字段通过本模块取真实数据，避免 accounts 直接依赖
画像/寝室/通知细节；所有查询按登录用户执行，不泄露 contact/email。
"""

from __future__ import annotations

from typing import Any

from apps.profiles.constants import QUESTIONNAIRE_VERSION


def _profile_of(user: Any) -> Any:
    """始终读库，避免请求间复用 ``user.profile`` 的陈旧反向缓存。"""
    from apps.profiles.models import Profile

    pk = getattr(user, "pk", None)
    if pk is None:
        return getattr(user, "profile", None)
    return Profile.objects.filter(user_id=pk).first()


def profile_completeness(user: Any) -> int:
    """本人画像完整度；无画像时为 0。"""
    profile = _profile_of(user)
    if profile is None:
        return 0
    try:
        return max(0, min(100, int(profile.completeness or 0)))
    except (TypeError, ValueError):
        return 0


def questionnaire_version(user: Any) -> str:
    """本人使用的问卷版本；无画像时返回当前版本。"""
    profile = _profile_of(user)
    return str(getattr(profile, "questionnaire_version", None) or QUESTIONNAIRE_VERSION)


def unread_count(user: Any) -> int:
    """未读通知数。"""
    from apps.notifications.models import Notification

    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def _user_summary(user: Any) -> dict[str, Any]:
    # 延迟导入避免 accounts.serializers ↔ profiles 的模块级循环。
    from apps.accounts.serializers import UserSummarySerializer

    return UserSummarySerializer(user).data


def _can_apply(room: Any, viewer: Any) -> bool:
    """本人能否申请该寝：已入寝/已有 ACTIVE 寝/有在途申请时均不可。"""
    from apps.connections.models import OPEN_STATUSES, ConnectionRequest
    from apps.rooms.models import Room, RoomMember

    if room.status != Room.Status.RECRUITING:
        return False
    if room.member_count >= room.capacity:
        return False
    if getattr(viewer, "gender", None) != room.gender:
        return False
    if getattr(viewer, "college", None) != room.college:
        return False
    memberships = RoomMember.objects.filter(user=viewer, status=RoomMember.Status.ACTIVE)
    if memberships.filter(room=room).exists():
        return False
    if memberships.exists():
        return False
    pending = ConnectionRequest.objects.filter(
        initiator=viewer,
        room=room,
        status__in=OPEN_STATUSES,
    ).exists()
    return not pending


def _pending_transfer(room: Any) -> dict[str, Any] | None:
    from apps.rooms.models import RoomTransfer

    transfer = (
        RoomTransfer.objects.filter(room=room, status=RoomTransfer.Status.PENDING)
        .select_related("from_owner", "to_member")
        .first()
    )
    if transfer is None:
        return None
    return {
        "id": transfer.pk,
        "status": transfer.status,
        "from_owner": _user_summary(transfer.from_owner),
        "to_member": _user_summary(transfer.to_member),
        "expires_at": transfer.expires_at,
        "created_at": transfer.created_at,
    }


def room_summary(user: Any) -> dict[str, Any] | None:
    """本人 ACTIVE 寝室的 RoomSummary（docs/04 §3.6）；无寝室返回 ``None``。"""
    from apps.rooms.models import RoomMember

    membership = (
        RoomMember.objects.filter(user=user, status=RoomMember.Status.ACTIVE)
        .select_related("room__owner")
        .first()
    )
    if membership is None:
        return None
    room = membership.room
    members = (
        RoomMember.objects.filter(room=room, status=RoomMember.Status.ACTIVE)
        .select_related("user")
        .order_by("created_at")[:6]
    )
    return {
        "code": room.code,
        "title": room.title,
        "capacity": room.capacity,
        "member_count": room.member_count,
        "status": room.status,
        "gender": room.gender,
        "college": room.college,
        "major": room.major,
        "tags": list(room.tags or []),
        "owner": _user_summary(room.owner),
        "member_preview": [_user_summary(member.user) for member in members],
        "can_apply": _can_apply(room, user),
        "my_role": membership.role,
        "pending_transfer": _pending_transfer(room),
    }
