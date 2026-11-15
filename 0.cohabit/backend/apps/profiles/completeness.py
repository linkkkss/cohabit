"""画像完整度 0–100（docs/03 §2.6、§10.3）。

完整度只用于“是否可匹配/创建请求”的门槛，不阻止保存；服务端计算并落库，
前端只展示。缺失路径用于 ``409 PROFILE_INCOMPLETE`` 的 ``detail.missing``。
"""

from __future__ import annotations

from typing import Any

from apps.profiles.constants import (
    HARD_OPTION_MAP,
    HARD_QUESTION_ORDER,
    MAX_TAGS,
    MIN_PROMPTS_FOR_COMPLETENESS,
    MIN_TAGS_FOR_COMPLETENESS,
    PROMPT_MAP,
    PROMPT_MAX_LENGTH,
    PROMPT_MAX_LINES,
    SOFT_QUESTION_ORDER,
    TAG_SET,
)
from apps.profiles.dims import soft_score

BASIC_SECTION_MAX = 20
HARD_SECTION_MAX = 20
SOFT_SECTION_MAX = 30
RED_LINE_SECTION_MAX = 10
TAG_SECTION_MAX = 10
PROMPT_SECTION_MAX = 10

_BASIC_FIELDS = ("nickname", "gender", "grade", "college", "major")
_VALID_GENDERS = {"MALE", "FEMALE"}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _basic_score(user: Any) -> int:
    if user is None:
        return 0
    score = 0
    if _text(getattr(user, "nickname", "")):
        score += 4
    if getattr(user, "gender", None) in _VALID_GENDERS:
        score += 4
    grade = getattr(user, "grade", None)
    if isinstance(grade, int) and not isinstance(grade, bool) and 1 <= grade <= 5:
        score += 4
    if _text(getattr(user, "college", "")):
        score += 4
    if _text(getattr(user, "major", "")):
        score += 4
    return score


def hard_answer_is_valid(question_key: str, value: Any) -> bool:
    """硬指标是否已回答且选项合法（含不进入六维的 alcohol/ac_temp）。"""
    options = HARD_OPTION_MAP.get(question_key)
    return bool(options) and isinstance(value, str) and value in options


def prompt_is_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not 1 <= len(text) <= PROMPT_MAX_LENGTH:
        return False
    return len(text.splitlines()) <= PROMPT_MAX_LINES


def _hard_section_score(hard_answers: dict[str, Any]) -> int:
    complete = all(
        hard_answer_is_valid(key, hard_answers.get(key))
        for key in HARD_QUESTION_ORDER
    )
    return HARD_SECTION_MAX if complete else 0


def _soft_section_score(soft_answers: dict[str, Any]) -> int:
    return sum(
        5
        for key in SOFT_QUESTION_ORDER
        if soft_score(soft_answers.get(key)) is not None
    )


def _tags_section_score(tags: list[Any]) -> int:
    if not MIN_TAGS_FOR_COMPLETENESS <= len(tags) <= MAX_TAGS:
        return 0
    if any(not isinstance(tag, str) or tag not in TAG_SET for tag in tags):
        return 0
    return TAG_SECTION_MAX


def _prompts_section_score(prompts: dict[str, Any]) -> int:
    if not MIN_PROMPTS_FOR_COMPLETENESS <= len(prompts) <= 3:
        return 0
    if any(key not in PROMPT_MAP or not prompt_is_valid(value) for key, value in prompts.items()):
        return 0
    return PROMPT_SECTION_MAX


def completeness_breakdown(
    user: Any,
    hard_answers: dict[str, Any] | None,
    soft_answers: dict[str, Any] | None,
    red_lines_confirmed: bool,
    tags: list[Any] | None,
    prompts: dict[str, Any] | None,
) -> dict[str, dict[str, int]]:
    """按 6 个区块返回 ``{name: {score, max}}``，便于前端进度环。"""
    hard_answers = hard_answers or {}
    soft_answers = soft_answers or {}
    tags = tags or []
    prompts = prompts or {}
    return {
        "basic": {"score": _basic_score(user), "max": BASIC_SECTION_MAX},
        "hard": {
            "score": _hard_section_score(hard_answers),
            "max": HARD_SECTION_MAX,
        },
        "soft": {
            "score": _soft_section_score(soft_answers),
            "max": SOFT_SECTION_MAX,
        },
        "red_lines": {
            "score": RED_LINE_SECTION_MAX if red_lines_confirmed is True else 0,
            "max": RED_LINE_SECTION_MAX,
        },
        "tags": {"score": _tags_section_score(tags), "max": TAG_SECTION_MAX},
        "prompts": {
            "score": _prompts_section_score(prompts),
            "max": PROMPT_SECTION_MAX,
        },
    }


def compute_completeness(
    user: Any,
    hard_answers: dict[str, Any] | None,
    soft_answers: dict[str, Any] | None,
    red_lines_confirmed: bool,
    tags: list[Any] | None,
    prompts: dict[str, Any] | None,
) -> int:
    """返回 0–100 的整数完整度（docs/03 §2.6 精确版）。"""
    breakdown = completeness_breakdown(
        user,
        hard_answers,
        soft_answers,
        red_lines_confirmed,
        tags,
        prompts,
    )
    total = sum(section["score"] for section in breakdown.values())
    return max(0, min(100, total))


def missing_profile_parts(
    user: Any,
    hard_answers: dict[str, Any] | None,
    soft_answers: dict[str, Any] | None,
    red_lines_confirmed: bool,
    tags: list[Any] | None,
    prompts: dict[str, Any] | None,
) -> list[str]:
    """返回缺失/非法区块的点路径（docs/03 §10.3 示例格式）。"""
    hard_answers = hard_answers or {}
    soft_answers = soft_answers or {}
    tags = tags or []
    prompts = prompts or {}
    missing: list[str] = []

    if user is not None:
        for field in _BASIC_FIELDS:
            value = getattr(user, field, None)
            if field == "grade":
                if not (isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5):
                    missing.append(field)
            elif field == "gender":
                if value not in _VALID_GENDERS:
                    missing.append(field)
            elif not _text(value):
                missing.append(field)

    for key in HARD_QUESTION_ORDER:
        if not hard_answer_is_valid(key, hard_answers.get(key)):
            missing.append(f"hard.{key}")
    for key in SOFT_QUESTION_ORDER:
        if soft_score(soft_answers.get(key)) is None:
            missing.append(f"soft.{key}")
    if red_lines_confirmed is not True:
        missing.append("red_lines_confirmed")
    if _tags_section_score(tags) == 0:
        missing.append("tags")
    if _prompts_section_score(prompts) == 0:
        missing.append("prompts")
    return missing
