"""匹配算法纯函数（docs/03 §8.3–§8.5）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.matching.algorithm import (
    common_tags,
    dimension_scores,
    red_line_conflicts,
    recommendation_reasons,
    score_pair,
    score_profiles,
    tag_bonus,
)
from apps.profiles.constants import DIMENSIONS
from apps.matching.exceptions import ProfileIncompleteError


def dims(**values: int) -> dict[str, int]:
    base = {dimension: 50 for dimension in DIMENSIONS}
    base.update(values)
    return base


def profile(
    uid: str,
    *,
    dims_value: dict[str, int] | None = None,
    tags: list[str] | None = None,
    red_lines: list[str] | None = None,
    hard_answers: dict[str, str] | None = None,
    version: str = "v1",
):
    return SimpleNamespace(
        user=SimpleNamespace(uid=uid),
        dims=dims_value or dims(),
        tags=tags or [],
        red_lines=red_lines or [],
        hard_answers=hard_answers or {},
        questionnaire_version=version,
        completeness=100,
    )


def test_identical_profiles_score_hundred():
    a = profile("0000000001")
    b = profile("0000000002")
    result = score_profiles(a, b)
    assert result["score"] == 100
    assert result["base"] == 100.0
    assert result["tag_bonus"] == 0
    assert result["red_penalty"] == 0
    assert result["conflicts"] == []
    assert result["version_warning"] is None
    assert result["dims"]["dim_score"] == {dimension: 100 for dimension in DIMENSIONS}


def test_base_weighted_formula():
    a = profile("0000000001")
    b = profile(
        "0000000002",
        dims_value=dims(social=50),
    )
    # social 分差 0? a.social=50, b.social=50 -> 100; 需要真实差异
    result = score_profiles(a, b)
    assert result["base"] == 100.0

    c = profile("0000000003", dims_value=dims(social=100))
    result = score_profiles(a, c)
    # social dim_score=50，weight=15 -> base=92.5
    assert result["base"] == 92.5
    assert result["score"] == 93


def test_tag_bonus_and_cap():
    a = profile("0000000001", tags=["早睡早起", "夜猫子", "猫派", "电影迷"])
    b = profile("0000000002", tags=["早睡早起", "夜猫子", "猫派", "电影迷"])
    assert common_tags(a, b) == ["早睡早起", "夜猫子", "猫派", "电影迷"]
    assert tag_bonus(a, b) == 6
    result = score_profiles(a, b)
    assert result["tag_bonus"] == 6
    assert result["score"] == 100  # 106 clamp


def test_tag_bonus_two_per_common_tag():
    a = profile("0000000001", tags=["夜猫子", "猫派"])
    b = profile("0000000002", tags=["夜猫子", "猫派", "电影迷"])
    assert tag_bonus(a, b) == 4


def test_red_line_conflicts_bidirectional():
    a = profile(
        "0000000001",
        red_lines=["smoke"],
        hard_answers={"smoke": "yes"},
    )
    b = profile(
        "0000000002",
        red_lines=["pet"],
        hard_answers={"smoke": "yes", "pet": "has_pet"},
    )
    # a 的红线 smoke 命中 b.smoke=yes；b 的红线 pet 命中 a.pet 缺失? a.pet 未设置 -> 只 1 条
    conflicts = red_line_conflicts(a, b)
    assert len(conflicts) == 1
    assert conflicts[0]["owner"] == "0000000001"
    assert conflicts[0]["red_line"] == "smoke"

    a.hard_answers["pet"] = "has_pet"
    conflicts = red_line_conflicts(a, b)
    assert len(conflicts) == 2
    assert {item["red_line"] for item in conflicts} == {"smoke", "pet"}


def test_red_conflict_caps_score_at_59():
    a = profile(
        "0000000001",
        red_lines=["smoke"],
        hard_answers={"smoke": "yes", "pet": "has_pet"},
    )
    b = profile(
        "0000000002",
        red_lines=["pet"],
        hard_answers={"smoke": "yes", "pet": "has_pet"},
    )
    result = score_profiles(a, b)
    assert len(result["conflicts"]) == 2
    assert result["red_penalty"] == 30
    assert result["score"] == 59


def test_same_red_line_counts_twice():
    a = profile("0000000001", red_lines=["smoke"], hard_answers={"smoke": "yes"})
    b = profile("0000000002", red_lines=["smoke"], hard_answers={"smoke": "yes"})
    result = score_profiles(a, b)
    assert len(result["conflicts"]) == 2
    assert result["score"] == 59


def test_ac_temp_conflict_threshold():
    a = profile("0000000001", red_lines=["ac_dc"], hard_answers={"ac_temp": "cool"})
    same = profile("0000000002", hard_answers={"ac_temp": "cool"})
    assert red_line_conflicts(a, same) == []

    c = profile("0000000003", hard_answers={"ac_temp": "warm"})
    conflicts = red_line_conflicts(a, c)
    assert len(conflicts) == 1
    assert conflicts[0]["red_line"] == "ac_dc"
    assert conflicts[0]["other_value"] == "warm"


def test_missing_hard_answer_does_not_trigger():
    a = profile("0000000001", red_lines=["smoke"])
    b = profile("0000000002", hard_answers={})
    assert red_line_conflicts(a, b) == []


def test_version_warning():
    a = profile("0000000001", version="v1")
    b = profile("0000000002", version="v1.1")
    result = score_profiles(a, b)
    assert result["version_warning"] == "对方问卷版本 v1.1，分数仅供参考"


def test_invalid_dims_raises():
    a = profile("0000000001", dims_value={"sleep": 100})
    b = profile("0000000002")
    with pytest.raises(ProfileIncompleteError):
        score_profiles(a, b)


def test_reasons_always_three():
    a = profile("0000000001")
    b = profile("0000000002")
    reasons = score_profiles(a, b)["reasons"]
    assert len(reasons) == 3
    assert all(len(reason) <= 60 for reason in reasons)


def test_reasons_skip_low_dimensions():
    reasons = recommendation_reasons(
        {dimension: 0 for dimension in DIMENSIONS},
        [],
    )
    assert reasons == ["你们的画像整体比较接近。"] * 3


def test_reasons_third_is_first_common_tag():
    a = profile(
        "0000000001",
        dims_value=dims(sleep=100, clean=100),
        tags=["夜猫子", "早睡早起"],
    )
    b = profile(
        "0000000002",
        dims_value=dims(sleep=100, clean=100),
        tags=["夜猫子", "早睡早起"],
    )
    reasons = recommendation_reasons(
        {**{dimension: 0 for dimension in DIMENSIONS}, "sleep": 100, "clean": 100},
        common_tags(a, b),
    )
    assert len(reasons) == 3
    assert "早睡早起" in reasons[2]


def test_dimension_scores():
    scores = dimension_scores(dims(sleep=100), dims(sleep=0))
    assert scores["sleep"] == 0
    assert scores["clean"] == 100


def test_score_pair_alias():
    assert score_pair is score_profiles
