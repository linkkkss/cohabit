"""匹配领域服务（docs/03 §8.2–§8.8）。

本模块只做编排：校验当前用户 → 解析目标 → 调用算法 → 排序。
不负责 HTTP 序列化（B6）与通知/审计（B4/B6）。
"""

from __future__ import annotations

from typing import Any

from apps.accounts.models import User
from apps.adminops.models import Block
from apps.connections.models import ConnectionRequest
from apps.matching import algorithm
from apps.matching.candidates import OPEN_STATUSES, candidate_list
from apps.matching.exceptions import (
    BlockedError,
    InvalidTargetError,
    MatchError,
    ProfileIncompleteError as MatchProfileIncompleteError,
    ProfileNotFoundError,
    TargetInRoomError,
    TargetProfileIncompleteError,
)
from apps.profiles.exceptions import (
    ProfileIncompleteError as ProfilesProfileIncompleteError,
)
from apps.profiles.dims import dims_are_valid
from apps.rooms.models import RoomMember

CANDIDATE_LIMIT = 200


def _profile_of(user: Any) -> Any:
    """读库取画像，避免跨请求复用 ``user.profile`` 的陈旧缓存。"""
    from apps.profiles.models import Profile

    pk = getattr(user, "pk", None)
    if pk is None:
        return getattr(user, "profile", None)
    return Profile.objects.filter(user_id=pk).first()


def _assert_seeker_ready(seeker: Any) -> Any:
    """当前用户必须是 ACTIVE/STUDENT 且画像 100 分。"""
    if seeker is None or getattr(seeker, "is_active", True) is not True:
        raise ProfileNotFoundError()
    if getattr(seeker, "status", None) != User.Status.ACTIVE:
        raise ProfileNotFoundError()
    if getattr(seeker, "role", None) != User.Role.STUDENT:
        raise ProfileNotFoundError()
    profile = _profile_of(seeker)
    if profile is None:
        raise MatchProfileIncompleteError(0)
    completeness = int(getattr(profile, "completeness", 0) or 0)
    if completeness < 100:
        missing = None
        from apps.profiles.completeness import missing_profile_parts

        try:
            missing = missing_profile_parts(
                seeker,
                getattr(profile, "hard_answers", {}) or {},
                getattr(profile, "soft_answers", {}) or {},
                bool(getattr(profile, "red_lines_confirmed", False)),
                getattr(profile, "tags", []) or [],
                getattr(profile, "prompts", {}) or {},
            )
        except Exception:  # pragma: no cover - 兜底，不阻塞错误返回
            missing = None
        raise MatchProfileIncompleteError(completeness, missing)
    if not dims_are_valid(getattr(profile, "dims", {}) or {}):
        raise MatchProfileIncompleteError(completeness)
    return profile


def _resolve_target(seeker: Any, uid: str) -> tuple[Any, Any]:
    """返回 (target_user, target_profile)，按 §8.7 抛领域异常。"""
    uid = str(uid or "").strip()
    if not uid:
        raise ProfileNotFoundError()
    if uid == getattr(seeker, "uid", None):
        raise InvalidTargetError("SELF")

    target = User.objects.filter(uid=uid).first()
    if target is None or getattr(target, "is_active", True) is not True:
        raise ProfileNotFoundError()
    if getattr(target, "status", None) != User.Status.ACTIVE:
        raise ProfileNotFoundError()
    if getattr(target, "role", None) != User.Role.STUDENT:
        raise ProfileNotFoundError()
    if (
        getattr(target, "college", None) != getattr(seeker, "college", None)
        or getattr(target, "gender", None) != getattr(seeker, "gender", None)
    ):
        raise ProfileNotFoundError()

    profile = _profile_of(target)
    completeness = int(getattr(profile, "completeness", 0) or 0) if profile else 0
    if profile is None or completeness < 100:
        raise TargetProfileIncompleteError(completeness)

    if RoomMember.objects.filter(
        user=target,
        status=RoomMember.Status.ACTIVE,
    ).exists():
        raise TargetInRoomError(uid)

    blocked = Block.objects.filter(blocker=seeker, blocked=target).exists() or (
        Block.objects.filter(blocker=target, blocked=seeker).exists()
    )
    if blocked:
        raise BlockedError()

    return target, profile


def score_target(seeker: Any, uid: str) -> dict[str, Any]:
    """单目标匹配分；返回 ``{target, profile, match}``。"""
    seeker_profile = _assert_seeker_ready(seeker)
    target, target_profile = _resolve_target(seeker, uid)
    try:
        result = algorithm.score_profiles(seeker_profile, target_profile)
    except (ProfilesProfileIncompleteError, MatchProfileIncompleteError) as exc:
        raise TargetProfileIncompleteError(target_profile.completeness) from exc
    return {"target": target, "profile": target_profile, "match": result}


def _sort_timestamp(profile: Any) -> float:
    value = getattr(profile, "updated_at", None)
    try:
        return float(value.timestamp())
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    profile = item["profile"]
    match = item["match"]
    return (
        -match["score"],
        -int(getattr(profile, "completeness", 0) or 0),
        -_sort_timestamp(profile),
        str(getattr(item["user"], "uid", "")),
    )


def match_list(seeker: Any) -> list[dict[str, Any]]:
    """候选列表：取有界候选池、算分并按 §8.2 排序。"""
    seeker_profile = _assert_seeker_ready(seeker)
    items: list[dict[str, Any]] = []
    for candidate in candidate_list(seeker, limit=CANDIDATE_LIMIT):
        profile = _profile_of(candidate)
        if profile is None:
            continue
        try:
            result = algorithm.score_profiles(seeker_profile, profile)
        except (ProfilesProfileIncompleteError, MatchProfileIncompleteError):
            continue
        items.append({"user": candidate, "profile": profile, "match": result})
    items.sort(key=_sort_key)
    return items


def has_open_request(user_a: Any, user_b: Any) -> bool:
    """两人之间是否已有在途请求（任一方向）。"""
    return ConnectionRequest.objects.filter(
        status__in=OPEN_STATUSES,
    ).filter(
        # 用 Q 对象避免链式 filter 的 AND 语义误伤
        **{"initiator": user_a, "target": user_b}
    ).exists() or ConnectionRequest.objects.filter(
        status__in=OPEN_STATUSES,
        initiator=user_b,
        target=user_a,
    ).exists()


def assert_can_match(seeker: Any, uid: str) -> dict[str, Any]:
    """供 API 在创建连接请求前复用的目标/自身校验。"""
    _assert_seeker_ready(seeker)
    target, profile = _resolve_target(seeker, uid)
    if has_open_request(seeker, target):
        raise MatchError("INVALID_STATE", status_code=409)
    return {"target": target, "profile": profile}
