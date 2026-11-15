"""匹配算法 v1（docs/03 §8.3–§8.5）。

纯函数：不查 DB、不写库；输入任意带问卷字段的对象（Profile 实例或 dict），
输出 ``score/base/tag_bonus/red_penalty/dims/reasons/conflicts/version_warning``。
"""

from __future__ import annotations

from typing import Any

from apps.profiles.constants import (
    AC_TEMP_CONFLICT_THRESHOLD,
    DIMENSION_WEIGHTS,
    DIMENSIONS,
    MAX_RED_CONFLICT_PENALTY,
    MAX_TAG_BONUS,
    RED_LINE_MAP,
    RED_LINE_ORDER,
    RED_LINE_CONFLICT_SCORE_CAP,
    RED_PENALTY_PER_CONFLICT,
    TAG_BONUS_PER_COMMON_TAG,
    TAG_ORDER,
)
from apps.profiles.dims import (
    dims_are_valid,
    hard_score,
    round_half_up,
    round_half_up_int,
)
from apps.matching.exceptions import ProfileIncompleteError

REASON_TEMPLATES = {
    "sleep": "你们的作息节奏很接近，早睡/早起冲突会少很多。",
    "clean": "整洁习惯高度一致，公共区摩擦会少很多。",
    "social": "社交热度接近，既能一起热闹也能各自安静。",
    "noise": "对声音的敏感度接近，耳机/外放分歧小。",
    "boundary": "边界感接近，访客和借东西的预期一致。",
    "spend": "公共开销分摊习惯接近，费用好商量。",
}
GENERIC_REASON = "你们的画像整体比较接近。"


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _uid(profile: Any) -> str:
    direct = _field(profile, "uid")
    if direct:
        return str(direct)
    user = _field(profile, "user")
    uid = _field(user, "uid") if user is not None else None
    return str(uid) if uid else ""


def _version(profile: Any) -> str:
    return str(_field(profile, "questionnaire_version", "v1") or "v1")


def _tags(profile: Any) -> list[str]:
    tags = _field(profile, "tags", []) or []
    return [tag for tag in tags if isinstance(tag, str)]


def _red_lines(profile: Any) -> list[str]:
    red_lines = _field(profile, "red_lines", []) or []
    return [item for item in red_lines if isinstance(item, str)]


def _hard_answers(profile: Any) -> dict[str, str]:
    answers = _field(profile, "hard_answers", {}) or {}
    return answers if isinstance(answers, dict) else {}


def _dims(profile: Any) -> dict[str, int]:
    dims = _field(profile, "dims", {}) or {}
    if not dims_are_valid(dims):
        raise ProfileIncompleteError(int(_field(profile, "completeness", 0) or 0))
    return dims


def dimension_scores(
    a_dims: dict[str, int],
    b_dims: dict[str, int],
) -> dict[str, int]:
    """``dim_score[d] = 100 - |a[d] - b[d]|``（0–100）。"""
    return {
        dimension: 100 - abs(a_dims[dimension] - b_dims[dimension])
        for dimension in DIMENSIONS
    }


def common_tags(a: Any, b: Any) -> list[str]:
    """共同标签，按 ``TAG_ORDER`` 排序。"""
    other = set(_tags(b))
    return [tag for tag in TAG_ORDER if tag in other and tag in set(_tags(a))]


def tag_bonus(a: Any, b: Any) -> int:
    return min(
        MAX_TAG_BONUS,
        TAG_BONUS_PER_COMMON_TAG * len(common_tags(a, b)),
    )


def _ac_temp_conflict(owner_answers: dict[str, str], other_answers: dict[str, str]) -> bool:
    owner_score = hard_score("ac_temp", owner_answers)
    other_score = hard_score("ac_temp", other_answers)
    if owner_score is None or other_score is None:
        return False
    return abs(owner_score - other_score) >= AC_TEMP_CONFLICT_THRESHOLD


def _red_line_hits(
    red_line_id: str,
    owner_answers: dict[str, str],
    other_answers: dict[str, str],
) -> tuple[bool, str | None]:
    spec = RED_LINE_MAP.get(red_line_id)
    if spec is None:
        return False, None
    if red_line_id == "ac_dc":
        return _ac_temp_conflict(owner_answers, other_answers), other_answers.get("ac_temp")
    other_value = other_answers.get(spec["question_key"])
    return other_value in spec["trigger_values"], other_value


def red_line_conflicts(a: Any, b: Any) -> list[dict[str, Any]]:
    """双向独立统计红线冲突；A 的红线命中 B、B 的红线命中 A 各计 1 次。"""
    a_answers = _hard_answers(a)
    b_answers = _hard_answers(b)
    conflicts: list[dict[str, Any]] = []
    for owner, owner_answers, other_answers in (
        (a, a_answers, b_answers),
        (b, b_answers, a_answers),
    ):
        owner_uid = _uid(owner)
        selected = set(_red_lines(owner))
        for red_line_id in RED_LINE_ORDER:
            if red_line_id not in selected:
                continue
            hit, other_value = _red_line_hits(
                red_line_id,
                owner_answers,
                other_answers,
            )
            if not hit:
                continue
            spec = RED_LINE_MAP[red_line_id]
            conflicts.append(
                {
                    "owner": owner_uid,
                    "red_line": red_line_id,
                    "label": spec["label"],
                    "other_value": other_value,
                    "message": spec["message"],
                }
            )
    return conflicts


def recommendation_reasons(
    dim_scores: dict[str, int],
    tags: list[str],
) -> list[str]:
    """按 docs/03 §8.5 生成 3 条理由；dim_score<50 的维度不选。"""
    ranked = sorted(
        (
            (DIMENSION_WEIGHTS[dimension] * dim_scores[dimension], dimension)
            for dimension in DIMENSIONS
        ),
        key=lambda item: (-item[0], DIMENSIONS.index(item[1])),
    )
    eligible = [dimension for _, dimension in ranked if dim_scores[dimension] >= 50]

    reasons: list[str] = []
    used: set[str] = set()
    for dimension in eligible[:2]:
        reasons.append(REASON_TEMPLATES[dimension])
        used.add(dimension)

    if tags:
        reasons.append(f"都有「{tags[0]}」标签，容易聊到一起。")

    if len(reasons) < 3:
        for dimension in eligible:
            if dimension in used:
                continue
            reasons.append(REASON_TEMPLATES[dimension])
            used.add(dimension)
            if len(reasons) == 3:
                break
    while len(reasons) < 3:
        reasons.append(GENERIC_REASON)
    return reasons[:3]


def score_profiles(a: Any, b: Any) -> dict[str, Any]:
    """计算一对画像的匹配结果（docs/03 §8.4/§8.6）。"""
    a_dims = _dims(a)
    b_dims = _dims(b)
    dim_scores = dimension_scores(a_dims, b_dims)

    base = sum(
        DIMENSION_WEIGHTS[dimension] * dim_scores[dimension]
        for dimension in DIMENSIONS
    ) / 100
    shared_tags = common_tags(a, b)
    bonus = min(MAX_TAG_BONUS, TAG_BONUS_PER_COMMON_TAG * len(shared_tags))
    conflicts = red_line_conflicts(a, b)
    penalty = min(MAX_RED_CONFLICT_PENALTY, RED_PENALTY_PER_CONFLICT * len(conflicts))

    raw = base + bonus - penalty
    score = max(0, min(100, round_half_up_int(raw)))
    if conflicts:
        score = min(score, RED_LINE_CONFLICT_SCORE_CAP)

    version_a = _version(a)
    version_b = _version(b)
    warning = None
    if version_a != version_b:
        warning = f"对方问卷版本 {version_b}，分数仅供参考"

    return {
        "score": score,
        "base": round_half_up(base, 1),
        "tag_bonus": bonus,
        "red_penalty": penalty,
        "dims": {
            "a": dict(a_dims),
            "b": dict(b_dims),
            "dim_score": dim_scores,
        },
        "reasons": recommendation_reasons(dim_scores, shared_tags),
        "conflicts": conflicts,
        "version_warning": warning,
    }


# B6/测试可用的别名。
score_pair = score_profiles
