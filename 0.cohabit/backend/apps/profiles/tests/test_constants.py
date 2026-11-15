"""问卷常量完整性（与 docs/03 §2–§7 冻结版一致）。"""

from __future__ import annotations

import pytest

from apps.profiles import constants as c


def test_question_counts():
    assert len(c.HARD_QUESTIONS) == 11
    assert len(c.HARD_QUESTION_ORDER) == 11
    assert len(c.SOFT_QUESTIONS) == 6
    assert len(c.RED_LINES) == 9
    assert len(c.TAG_ORDER) == 42
    assert len(c.PROMPTS) == 6


def test_hard_question_order():
    assert c.HARD_QUESTION_ORDER == (
        "smoke",
        "sleep_time",
        "wake_time",
        "late_return",
        "snore",
        "pet",
        "visitor_freq",
        "alcohol",
        "game_noise",
        "ac_temp",
        "clean_freq",
    )


def test_hard_options_are_unique_and_scores_valid():
    for question in c.HARD_QUESTIONS:
        values = [option["value"] for option in question["options"]]
        assert len(values) == len(set(values)), question["key"]
        for option in question["options"]:
            if question["key"] in {"alcohol", "ac_temp"}:
                continue
            assert option["score"] in {0, 35, 40, 50, 70, 75, 80, 100}
            assert 0 <= option["score"] <= 100


def test_alcohol_and_ac_temp_have_no_dimension():
    assert c.HARD_QUESTION_MAP["alcohol"]["dimension"] is None
    assert c.HARD_QUESTION_MAP["ac_temp"]["dimension"] is None
    assert c.HARD_SCORE_MAP["alcohol"] == {}
    assert c.HARD_SCORE_MAP["ac_temp"] == {"cool": 0, "medium": 50, "warm": 100}


def test_dimensions_and_weights():
    assert c.DIMENSIONS == ("sleep", "clean", "social", "noise", "boundary", "spend")
    assert sum(c.DIMENSION_WEIGHTS.values()) == 100
    assert set(c.DIMENSION_WEIGHTS) == set(c.DIMENSIONS)


def test_tags_unique_and_grouped():
    assert len(c.TAG_SET) == 42
    assert len(c.TAG_ORDER) == len(set(c.TAG_ORDER))
    assert sum(len(tags) for _, tags in c.TAG_GROUPS) == 42
    assert c.TAG_GROUP_MAP["夜猫子"] == "作息"


def test_red_lines():
    assert c.RED_LINE_ORDER[0] == "smoke"
    assert c.RED_LINE_MAP["ac_dc"]["trigger_values"] == ()
    assert c.RED_LINE_MAP["pet"]["trigger_values"] == ("has_pet",)
    assert c.AC_TEMP_CONFLICT_THRESHOLD == 50
    for red_line in c.RED_LINES:
        assert red_line["question_key"] in c.HARD_QUESTION_MAP


def test_prompts():
    assert c.PROMPT_ORDER == (
        "weekend",
        "small_thing",
        "vibe",
        "cannot_accept",
        "visitor_expect",
        "sleep_summary",
    )
    assert all(item["max_length"] == 120 for item in c.PROMPTS)


def test_questionnaire_payload_shape():
    payload = c.questionnaire_payload()
    assert payload["version"] == "v1"
    assert len(payload["hard"]) == 11
    assert len(payload["soft"]) == 6
    assert len(payload["red_lines"]) == 9
    assert len(payload["tags"]) == 42
    assert len(payload["prompts"]) == 6
    assert payload["soft"][0]["labels"]["1"]


@pytest.mark.parametrize(
    ("tag", "expected"),
    [("早睡早起", 0), ("可以分享", 41), ("不存在", 42)],
)
def test_tag_sort_key(tag, expected):
    assert c.tag_sort_key(tag) == expected
