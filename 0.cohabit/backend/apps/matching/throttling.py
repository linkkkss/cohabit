"""匹配 API 限频（docs/04 §1.9：单目标评分 60 次/小时）。"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

from apps.accounts.exceptions import ApiError

SCORE_LIMIT = 60
SCORE_WINDOW_SECONDS = 3600


def _key(user: Any) -> str:
    uid = str(getattr(user, "uid", "") or getattr(user, "pk", ""))
    return f"match:score:{uid}"


def enforce_score_limit(user: Any) -> None:
    """同一用户每小时最多 60 次评分；超限抛 429 ``RATE_LIMITED``。"""
    key = _key(user)
    count = int(cache.get(key) or 0)
    if count >= SCORE_LIMIT:
        raise ApiError("RATE_LIMITED", status_code=429, retry_after=SCORE_WINDOW_SECONDS)
    cache.set(key, count + 1, SCORE_WINDOW_SECONDS)
