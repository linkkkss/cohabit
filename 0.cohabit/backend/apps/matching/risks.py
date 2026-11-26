"""候选人风险摘要（候选卡的“一句话风险”，docs/03 §8 的展示层补充）。

匹配分是 0–100 的连续值，用户很难从分数里读出“到底差在哪”。这里把最影响
共同生活的三项差异翻成一句人话：

* **作息**：把 ``sleep_time`` 的选项映射成代表时点，按环形差算相差小时数；
* **整洁**：用 ``clean`` 维度的差值判断“差异较大”；
* **红线**：双方 ``conflicts`` 非空时说明有几项。

只做展示：不参与打分，也不改变 :func:`apps.matching.algorithm.score_profiles`
的输出；未答/数据缺失时静默跳过，绝不因为展示而抛错。
"""

from __future__ import annotations

from typing import Any

# ``sleep_time`` 选项 → 代表时点（24 小时制，浮点小时）。
SLEEP_HOURS: dict[str, float] = {
    "before23": 22.0,
    "23_00": 23.5,
    "00_01": 0.5,
    "after01": 2.0,
}

# 相差不到 2 小时算“能磨合”，不提示；整洁差 30 分以上才提示。
SLEEP_GAP_HOURS = 2.0
CLEAN_GAP_POINTS = 30


def _sleep_hour(profile: Any) -> float | None:
    """读出 ``sleep_time`` 的代表时点；未答/取值未知返回 ``None``。"""
    answers = getattr(profile, "hard_answers", None) or {}
    value = answers.get("sleep_time")
    if not isinstance(value, str):
        return None
    return SLEEP_HOURS.get(value)


def _circular_gap(left: float, right: float) -> float:
    """一天为周期的差值：22:00 与 02:00 相差 4 小时，而不是 20 小时。"""
    diff = abs(left - right) % 24
    return min(diff, 24 - diff)


def format_hours(hours: float) -> str:
    """1.5 → ``1.5 小时``，4.0 → ``4 小时``（避免出现 ``4.0 小时``）。"""
    if abs(hours - round(hours)) < 0.25:
        return f"{int(round(hours))} 小时"
    return f"{hours:.1f} 小时"


def _clean_gap(match: dict[str, Any]) -> int:
    """``clean`` 维度的差值（0–100）；取不到时视为无差异。"""
    dims = match.get("dims") or {}
    scores = dims.get("dim_score") or {}
    value = scores.get("clean")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return max(0, int(round(100 - float(value))))


def risk_items(
    seeker_profile: Any,
    target_profile: Any,
    match: dict[str, Any],
) -> list[dict[str, str]]:
    """返回按严重程度排序的风险条目 ``[{code, text}]``，可能为空列表。"""
    items: list[dict[str, str]] = []

    conflicts = match.get("conflicts") or []
    if conflicts:
        items.append(
            {
                "code": "red_line",
                "text": f"存在 {len(conflicts)} 项红线冲突",
            }
        )

    left = _sleep_hour(seeker_profile)
    right = _sleep_hour(target_profile)
    if left is not None and right is not None:
        gap = _circular_gap(left, right)
        if gap >= SLEEP_GAP_HOURS:
            items.append(
                {
                    "code": "sleep_gap",
                    "text": f"作息相差 {format_hours(gap)}",
                }
            )

    if _clean_gap(match) >= CLEAN_GAP_POINTS:
        items.append({"code": "clean_gap", "text": "整洁度差异较大"})

    return items
