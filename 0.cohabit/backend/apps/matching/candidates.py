"""匹配候选池（docs/03 §8.2、§8.8）。

ORM 查询与纯判定分开：``is_candidate`` 便于单测；``candidate_queryset`` 供
API 层分页取 200 个候选后在内存算分。
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.adminops.models import Block
from apps.connections.models import ConnectionRequest
from apps.rooms.models import RoomMember

# B5 之前表可能尚未创建；本模块只定义查询，不在 import 时访问数据库。
OPEN_STATUSES = (
    ConnectionRequest.Status.PENDING,
    ConnectionRequest.Status.CONTACT_SHARED,
    ConnectionRequest.Status.CONFIRMING,
)


def _user_id(value: Any) -> Any:
    return getattr(value, "pk", value)


def is_candidate(
    seeker: Any,
    candidate: Any,
    *,
    candidate_profile: Any = None,
    has_active_room: bool = False,
    blocked: bool = False,
    inflight: bool = False,
) -> bool:
    """纯判定：候选是否满足 §8.2 的硬过滤（DB 事实由调用方传入）。"""
    if seeker is None or candidate is None:
        return False
    if _user_id(seeker) == _user_id(candidate):
        return False
    if getattr(candidate, "status", None) != User.Status.ACTIVE:
        return False
    if getattr(candidate, "role", None) != User.Role.STUDENT:
        return False
    if getattr(candidate, "is_active", True) is not True:
        return False
    if getattr(candidate, "college", None) != getattr(seeker, "college", None):
        return False
    if getattr(candidate, "gender", None) != getattr(seeker, "gender", None):
        return False
    if candidate_profile is None:
        candidate_profile = getattr(candidate, "profile", None)
    if candidate_profile is None or getattr(candidate_profile, "completeness", None) != 100:
        return False
    if has_active_room or blocked or inflight:
        return False
    return True


def candidate_queryset(seeker: Any) -> QuerySet[User]:
    """同院同性别、画像完整、无 ACTIVE 寝、未拉黑、无在途请求的候选池。"""
    queryset = (
        User.objects.filter(
            status=User.Status.ACTIVE,
            role=User.Role.STUDENT,
            is_active=True,
            college=seeker.college,
            gender=seeker.gender,
        )
        .exclude(pk=seeker.pk)
        .filter(profile__completeness=100)
        .select_related("profile")
    )

    active_member_ids = RoomMember.objects.filter(
        status=RoomMember.Status.ACTIVE,
    ).values("user_id")
    queryset = queryset.exclude(pk__in=active_member_ids)

    blocked_out = Block.objects.filter(blocker=seeker).values("blocked_id")
    blocked_in = Block.objects.filter(blocked=seeker).values("blocker_id")
    queryset = queryset.exclude(pk__in=blocked_out).exclude(pk__in=blocked_in)

    open_requests = ConnectionRequest.objects.filter(status__in=OPEN_STATUSES)
    outgoing = open_requests.filter(initiator=seeker).values("target_id")
    incoming = open_requests.filter(target=seeker).values("initiator_id")
    queryset = queryset.exclude(pk__in=outgoing).exclude(pk__in=incoming)
    return queryset


def candidate_list(seeker: Any, limit: int = 200) -> list[User]:
    """先取有界候选（默认 200），再由 service 算分排序。"""
    return list(candidate_queryset(seeker)[:limit])
