"""完整度计算与缺失路径（docs/03 §2.6、§10.3）。"""

from __future__ import annotations

from apps.profiles.completeness import (
    completeness_breakdown,
    compute_completeness,
    hard_answer_is_valid,
    missing_profile_parts,
    prompt_is_valid,
)
from apps.profiles.tests.helpers import (
    full_hard,
    full_prompts,
    full_soft,
    full_tags,
    make_user,
)


def test_empty_profile_is_twenty():
    assert compute_completeness(make_user(), {}, {}, False, [], {}) == 20


def test_full_profile_is_hundred():
    score = compute_completeness(
        make_user(),
        full_hard(),
        full_soft(),
        True,
        full_tags(),
        full_prompts(),
    )
    assert score == 100


def test_breakdown_sections():
    breakdown = completeness_breakdown(
        make_user(),
        full_hard(),
        full_soft(),
        True,
        full_tags(),
        full_prompts(),
    )
    assert breakdown["basic"] == {"score": 20, "max": 20}
    assert breakdown["hard"] == {"score": 20, "max": 20}
    assert breakdown["soft"] == {"score": 30, "max": 30}
    assert breakdown["red_lines"] == {"score": 10, "max": 10}
    assert breakdown["tags"] == {"score": 10, "max": 10}
    assert breakdown["prompts"] == {"score": 10, "max": 10}


def test_missing_major_costs_four():
    score = compute_completeness(
        make_user(major=""),
        full_hard(),
        full_soft(),
        True,
        full_tags(),
        full_prompts(),
    )
    assert score == 96


def test_hard_is_all_or_nothing():
    hard = full_hard()
    hard.pop("smoke")
    score = compute_completeness(
        make_user(),
        hard,
        full_soft(),
        True,
        full_tags(),
        full_prompts(),
    )
    assert score == 80


def test_soft_scores_five_each():
    soft = full_soft()
    soft.pop("social")
    score = compute_completeness(
        make_user(),
        full_hard(),
        soft,
        True,
        full_tags(),
        full_prompts(),
    )
    assert score == 95


def test_red_lines_confirmed_is_ten():
    score = compute_completeness(
        make_user(),
        full_hard(),
        full_soft(),
        False,
        full_tags(),
        full_prompts(),
    )
    assert score == 90


def test_tags_need_three_and_valid():
    two = compute_completeness(
        make_user(),
        full_hard(),
        full_soft(),
        True,
        full_tags(2),
        full_prompts(),
    )
    assert two == 90
    invalid = compute_completeness(
        make_user(),
        full_hard(),
        full_soft(),
        True,
        ["不存在", "夜猫子", "早睡早起"],
        full_prompts(),
    )
    assert invalid == 90


def test_prompts_need_two_and_valid():
    one = compute_completeness(
        make_user(),
        full_hard(),
        full_soft(),
        True,
        full_tags(),
        full_prompts(1),
    )
    assert one == 90


def test_hard_answer_is_valid():
    assert hard_answer_is_valid("smoke", "no")
    assert hard_answer_is_valid("smoke", "sometimes")
    assert not hard_answer_is_valid("smoke", "nope")
    assert not hard_answer_is_valid("unknown", "no")


def test_prompt_is_valid():
    assert prompt_is_valid("正常回答")
    assert prompt_is_valid("第一行\n第二行")
    assert not prompt_is_valid("")
    assert not prompt_is_valid("   ")
    assert not prompt_is_valid("a" * 121)
    assert not prompt_is_valid("一\n二\n三\n四")
    assert not prompt_is_valid(123)


def test_missing_paths_for_empty_profile():
    missing = missing_profile_parts(make_user(major=""), {}, {}, False, [], {})
    assert "major" in missing
    assert "hard.smoke" in missing
    assert "soft.clean" in missing
    assert "red_lines_confirmed" in missing
    assert "tags" in missing
    assert "prompts" in missing
    assert len(missing) == 1 + 11 + 6 + 1 + 1 + 1


def test_no_missing_when_complete():
    assert (
        missing_profile_parts(
            make_user(),
            full_hard(),
            full_soft(),
            True,
            full_tags(),
            full_prompts(),
        )
        == []
    )
