"""六维画像分计算（docs/03 §2.5、§4.2、§8.3）。

纯函数：不读写数据库、不依赖 Django。服务端保存画像与匹配计算共用同一套
公式，保证 ``Profile.dims`` 与匹配分数一致。

说明：docs/03 §8.3 明确定义 ``round_half_up``，本模块按“四舍五入（.5 进位）”
实现；03 §2.2/§2.7 的 boundary 示例已按该规则校正为 75。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from apps.profiles.constants import (
    DIMENSIONS,
    HARD_SCORE_MAP,
    SOFT_MAX,
    SOFT_MIN,
)

SOFT_WEIGHT: Final = 0.7
HARD_WEIGHT: Final = 0.3


def round_half_up(value: float | int, digits: int = 0) -> float:
    """按十进制四舍五入（.5 远离零）到 ``digits`` 位小数。

    使用 ``Decimal(str(value))`` 避免二进制浮点误差把 74.5 变成 74.499…。
    """
    quantum = Decimal(1).scaleb(-digits)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return float(rounded)


def round_half_up_int(value: float | int) -> int:
    return int(round_half_up(value, 0))


def soft_score(value: int | None) -> int | None:
    """软指标 1–5 映射到 0/25/50/75/100；非法/缺失返回 ``None``。

    ``bool`` 是 ``int`` 的子类，必须显式排除。
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not SOFT_MIN <= value <= SOFT_MAX:
        return None
    return (value - 1) * 25


def hard_score(question_key: str, answers: dict[str, str] | None) -> int | None:
    """按题 key + 选项 value 查硬指标 0–100 分；未答/非法返回 ``None``。"""
    if not answers:
        return None
    value = answers.get(question_key)
    if not isinstance(value, str):
        return None
    scores = HARD_SCORE_MAP.get(question_key)
    if not scores:
        return None
    return scores.get(value)


def _hard_average(answers: dict[str, str] | None, keys: tuple[str, ...]) -> float | None:
    """维度所需硬指标全部有合法分值时取算术平均，否则视为未答。"""
    if not answers or any(key not in answers for key in keys):
        return None
    scores = [hard_score(key, answers) for key in keys]
    if any(score is None for score in scores):
        return None
    return sum(score for score in scores if score is not None) / len(keys)


def _mix(
    soft_value: int | None,
    hard_value: float | None,
) -> int:
    """按 0.7/0.3 加权；缺一项时把权重全部让给另一项（docs/03 §8.3）。"""
    parts: list[tuple[float, float]] = []
    if soft_value is not None:
        parts.append((float(soft_value), SOFT_WEIGHT))
    if hard_value is not None:
        parts.append((hard_value, HARD_WEIGHT))
    if not parts:
        return 0
    total_weight = sum(weight for _, weight in parts)
    weighted = sum(value * weight for value, weight in parts)
    return round_half_up_int(weighted / total_weight)


def compute_dims(
    hard_answers: dict[str, str] | None,
    soft_answers: dict[str, int] | None,
) -> dict[str, int]:
    """返回六维整数（0–100），键固定为 ``DIMENSIONS``。"""
    hard_answers = hard_answers or {}
    soft_answers = soft_answers or {}
    soft = lambda key: soft_score(soft_answers.get(key))  # noqa: E731 - 局部查表
    return {
        "sleep": _mix(
            soft("sleep_regular"),
            _hard_average(hard_answers, ("sleep_time", "wake_time", "late_return")),
        ),
        "clean": _mix(soft("clean"), _hard_average(hard_answers, ("clean_freq",))),
        "social": soft("social") or 0,
        "noise": _mix(
            soft("noise"),
            _hard_average(hard_answers, ("snore", "game_noise")),
        ),
        "boundary": _mix(
            soft("boundary"),
            _hard_average(hard_answers, ("smoke", "pet", "visitor_freq")),
        ),
        "spend": soft("spend") or 0,
    }


def dims_are_valid(dims: object) -> bool:
    """校验六维对象：六键齐全、值为 0–100 的整数（拒绝 bool/浮点/字符串）。"""
    if not isinstance(dims, dict):
        return False
    if set(dims) != set(DIMENSIONS):
        return False
    for value in dims.values():
        if isinstance(value, bool) or not isinstance(value, int):
            return False
        if not 0 <= value <= 100:
            return False
    return True
