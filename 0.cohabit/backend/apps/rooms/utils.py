"""rooms 服务层共用的小工具：时间序列化、标签规范化、寝室标题。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

TITLE_MAX_LENGTH = 30
TAGS_MAX = 8
TAG_MAX_LENGTH = 20


def isoformat(value: datetime | None) -> str:
    """UTC ISO8601（``...Z``）：通知 payload / 审计 meta 只放字符串时间。"""
    if value is None:
        return ""
    if value.tzinfo is None:
        from django.utils import timezone

        value = timezone.make_aware(value, timezone.get_current_timezone())
    from datetime import timezone as dt_timezone

    return value.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_tags(tags: Any, *, limit: int = TAGS_MAX) -> list[str]:
    """把任意输入规范化为 ``list[str]``：去空白、去空串、去重、限长限量。"""
    if tags is None:
        return []
    if isinstance(tags, (str, bytes)):
        candidates: Iterable[Any] = [tags]
    elif isinstance(tags, Iterable):
        candidates = tags
    else:
        candidates = [tags]

    result: list[str] = []
    for item in candidates:
        text = str(item).strip()[:TAG_MAX_LENGTH]
        if not text or text in result:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def merge_tags(*groups: Any, limit: int = TAGS_MAX) -> list[str]:
    """按顺序合并多组标签并去重（docs/02 §3.5.4：双方 tags 合并 ≤8）。"""
    merged: list[str] = []
    for group in groups:
        for tag in normalize_tags(group, limit=limit):
            if tag not in merged:
                merged.append(tag)
            if len(merged) >= limit:
                return merged
    return merged


def default_room_title(owner: Any) -> str:
    """``"{nickname}的寝室"``，截断到 30 字（docs/02 §3.5.4）。"""
    nickname = str(getattr(owner, "nickname", "") or "").strip() or "我"
    return f"{nickname}的寝室"[:TITLE_MAX_LENGTH]


def merge_pair_tags(initiator: Any, target: Any) -> list[str]:
    """人-人建寝时合并双方画像标签（画像不存在则按空处理）。"""
    from apps.profiles.models import Profile

    tags: list[Any] = []
    for user in (initiator, target):
        pk = getattr(user, "pk", None)
        if pk is None:
            continue
        profile = Profile.objects.filter(user_id=pk).only("tags").first()
        if profile is not None and isinstance(profile.tags, list):
            tags.extend(profile.tags)
    return normalize_tags(tags)
