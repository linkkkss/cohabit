"""匹配结果序列化（docs/04 §3.4 MatchScore）。"""

from __future__ import annotations

from typing import Any

from apps.accounts.serializers import UserSummarySerializer
from apps.profiles.serializers import headline_for


def match_target_payload(user: Any, profile: Any) -> dict[str, Any]:
    """MatchScore.target：公开摘要 + 画像完整度/标签/headline。"""
    payload: dict[str, Any] = dict(UserSummarySerializer(user).data)
    payload.update(
        {
            "completeness": int(getattr(profile, "completeness", 0) or 0),
            "tags": list(getattr(profile, "tags", None) or []),
            "headline": headline_for(profile),
        }
    )
    return payload


def match_score_payload(user: Any, profile: Any, match: dict[str, Any]) -> dict[str, Any]:
    """把 ``algorithm.score_profiles`` 的结果组装为 §3.4 响应体。"""
    return {
        "target": match_target_payload(user, profile),
        "score": int(match.get("score", 0) or 0),
        "base": match.get("base", 0),
        "tag_bonus": match.get("tag_bonus", 0),
        "red_penalty": match.get("red_penalty", 0),
        "dims": match.get("dims", {}),
        "reasons": list(match.get("reasons", []) or []),
        "conflicts": list(match.get("conflicts", []) or []),
        "version_warning": match.get("version_warning"),
    }


__all__ = ["match_score_payload", "match_target_payload"]
