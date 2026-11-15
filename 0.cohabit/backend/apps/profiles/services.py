"""画像服务：校验 → 计算 dims/completeness → 单事务落库（docs/03 §2.5）。"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.profiles.completeness import compute_completeness
from apps.profiles.constants import QUESTIONNAIRE_VERSION
from apps.profiles.dims import compute_dims
from apps.profiles.models import Profile
from apps.profiles.validation import ProfileData, validate_profile_payload

PROFILE_FIELDS = (
    "hard_answers",
    "soft_answers",
    "red_lines",
    "red_lines_confirmed",
    "tags",
    "prompts",
)


def get_profile(user: Any) -> Profile | None:
    return Profile.objects.filter(user=user).first()


def _compute(profile: Profile, data: ProfileData) -> dict[str, Any]:
    dims = compute_dims(data.hard_answers, data.soft_answers)
    completeness = compute_completeness(
        profile.user,
        data.hard_answers,
        data.soft_answers,
        data.red_lines_confirmed,
        data.tags,
        data.prompts,
    )
    return {"dims": dims, "completeness": completeness}


def save_profile(
    user: Any,
    payload: Any,
    *,
    partial: bool = False,
) -> Profile:
    """保存画像（PUT ``partial=False`` / PATCH ``partial=True``）。

    校验失败不落库；``dims``/``completeness`` 始终由服务端重算，客户端提交值忽略。
    """
    with transaction.atomic():
        profile = (
            Profile.objects.select_for_update()
            .select_related("user")
            .filter(user=user)
            .first()
        )
        data = validate_profile_payload(payload, partial=partial, existing=profile)
        if profile is None:
            profile = Profile(user=user)

        for field_name in PROFILE_FIELDS:
            setattr(profile, field_name, getattr(data, field_name))
        profile.questionnaire_version = data.questionnaire_version

        computed = _compute(profile, data)
        profile.dims = computed["dims"]
        profile.completeness = computed["completeness"]
        profile.save()
    return profile


def update_profile(user: Any, payload: Any) -> Profile:
    """PATCH 语义的便捷入口。"""
    return save_profile(user, payload, partial=True)


def recompute_profile(profile: Profile, *, save: bool = True) -> Profile:
    """按落库答案重算 dims/completeness（命令 ``recompute_profiles`` 复用）。"""
    data = ProfileData(
        hard_answers=profile.hard_answers or {},
        soft_answers=profile.soft_answers or {},
        red_lines=profile.red_lines or [],
        red_lines_confirmed=profile.red_lines_confirmed is True,
        tags=profile.tags or [],
        prompts=profile.prompts or {},
        questionnaire_version=profile.questionnaire_version or QUESTIONNAIRE_VERSION,
    )
    computed = _compute(profile, data)
    profile.dims = computed["dims"]
    profile.completeness = computed["completeness"]
    if save:
        profile.save(update_fields=["dims", "completeness", "updated_at"])
    return profile


def profile_is_complete(profile: Profile | None) -> bool:
    return profile is not None and profile.completeness == 100


def profile_questionnaire(profile: Profile) -> dict[str, Any]:
    """返回画像的问卷区块（供 API 序列化复用，不含 user 基本资料）。"""
    return {
        "hard_answers": profile.hard_answers or {},
        "soft_answers": profile.soft_answers or {},
        "red_lines": profile.red_lines or [],
        "red_lines_confirmed": profile.red_lines_confirmed,
        "tags": profile.tags or [],
        "prompts": profile.prompts or {},
        "dims": profile.dims or {},
        "completeness": profile.completeness,
        "questionnaire_version": profile.questionnaire_version,
    }


def public_profile(target: Any, viewer: Any) -> Any:
    """``GET /api/users/:uid`` 的目标解析（docs/04 §4.2）。

    同院同性别且未被拉黑；否则统一 404 ``PROFILE_NOT_FOUND``（不泄露存在性），
    拉黑关系返回 403 ``BLOCKED``。目标画像是否完整不做限制（响应带 completeness）。
    """
    from django.db.models import Q

    from apps.accounts.models import User
    from apps.adminops.models import Block
    from apps.matching.exceptions import BlockedError, ProfileNotFoundError

    uid = str(target or "").strip()
    found = User.objects.filter(uid=uid).first() if uid else None
    if found is None or getattr(found, "is_active", True) is not True:
        raise ProfileNotFoundError()
    if getattr(found, "status", None) != User.Status.ACTIVE:
        raise ProfileNotFoundError()
    if getattr(found, "role", None) != User.Role.STUDENT:
        raise ProfileNotFoundError()
    if (
        getattr(found, "college", None) != getattr(viewer, "college", None)
        or getattr(found, "gender", None) != getattr(viewer, "gender", None)
    ):
        raise ProfileNotFoundError()

    blocked = Block.objects.filter(
        Q(blocker=viewer, blocked=found) | Q(blocker=found, blocked=viewer)
    ).exists()
    if blocked:
        raise BlockedError()
    return found

