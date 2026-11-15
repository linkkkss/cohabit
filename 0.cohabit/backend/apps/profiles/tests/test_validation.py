"""问卷写入校验与 PUT/PATCH 归一化（docs/03 §2.3–§2.4）。"""

from __future__ import annotations

import pytest

from apps.profiles.exceptions import (
    PayloadTooLargeError,
    ProfileValidationError,
)
from apps.profiles.tests.helpers import (
    full_hard,
    full_payload,
    full_prompts,
    full_soft,
    full_tags,
)
from apps.profiles.validation import (
    ProfileData,
    validate_profile_payload,
)


def _codes(exc: ProfileValidationError) -> dict[str, str]:
    return {path: err["code"] for path, err in exc.value.fields.items()}


def test_put_empty_payload_is_all_empty():
    data = validate_profile_payload({}, partial=False)
    assert data == ProfileData()
    assert data.questionnaire_version == "v1"


def test_put_full_payload():
    data = validate_profile_payload(full_payload(), partial=False)
    assert data.hard_answers == full_hard()
    assert data.soft_answers == full_soft(3)
    assert data.red_lines == ["smoke", "pet"]
    assert data.red_lines_confirmed is True
    assert data.tags == list(full_tags())
    assert data.prompts == full_prompts()


def test_put_ignores_server_fields():
    payload = {**full_payload(), "dims": {"sleep": 99}, "completeness": 1}
    data = validate_profile_payload(payload, partial=False)
    assert not hasattr(data, "dims")
    assert not hasattr(data, "completeness")


def test_unknown_hard_key():
    payload = {**full_payload(), "hard_answers": {"nope": "no"}}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["hard_answers.nope"] == "UNKNOWN_ANSWER_KEY"


def test_invalid_hard_option():
    payload = {**full_payload(), "hard_answers": {"smoke": "nope"}}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["hard_answers.smoke"] == "INVALID_OPTION"


def test_soft_must_be_integer_not_bool():
    for bad in (True, "4", 4.0, 0, 6):
        payload = {**full_payload(), "soft_answers": {"clean": bad}}
        with pytest.raises(ProfileValidationError) as exc:
            validate_profile_payload(payload, partial=False)
        assert _codes(exc)["soft_answers.clean"] == "INVALID_SOFT_VALUE"


def test_unknown_soft_key():
    payload = {**full_payload(), "soft_answers": {"nope": 3}}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["soft_answers.nope"] == "UNKNOWN_ANSWER_KEY"


def test_invalid_red_line():
    payload = {**full_payload(), "red_lines": ["nope"]}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["red_lines"] == "INVALID_RED_LINE"


def test_red_line_deduplicates_and_sorts():
    payload = {**full_payload(), "red_lines": ["pet", "smoke", "pet"]}
    data = validate_profile_payload(payload, partial=False)
    assert data.red_lines == ["smoke", "pet"]


def test_red_line_confirmed_must_be_bool():
    payload = {**full_payload(), "red_lines_confirmed": "true"}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["red_lines_confirmed"] == "INVALID_BOOLEAN"


def test_tag_limit():
    payload = {**full_payload(), "tags": list(full_tags()) + ["猫派", "狗派", "二次元", "电影迷", "音乐现场", "阅读"]}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["tags"] == "TAG_LIMIT"


def test_invalid_tag():
    payload = {**full_payload(), "tags": ["不存在的标签"]}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["tags"] == "INVALID_TAG"


def test_tags_deduplicate_and_sort():
    payload = {**full_payload(), "tags": ["夜猫子", "早睡早起", "夜猫子"]}
    data = validate_profile_payload(payload, partial=False)
    assert data.tags == ["早睡早起", "夜猫子"]


def test_unknown_prompt_key():
    payload = {**full_payload(), "prompts": {"nope": "回答"}}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["prompts.nope"] == "INVALID_PROMPT_KEY"


def test_prompt_too_long():
    payload = {**full_payload(), "prompts": {"weekend": "a" * 121}}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["prompts.weekend"] == "PROMPT_TOO_LONG"


def test_prompt_too_many_lines():
    payload = {**full_payload(), "prompts": {"weekend": "一\n二\n三\n四"}}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["prompts.weekend"] == "INVALID_TEXT"


def test_prompt_html_rejected():
    payload = {**full_payload(), "prompts": {"weekend": "<b>hi</b>"}}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["prompts.weekend"] == "INVALID_TEXT"


def test_prompt_trimmed():
    payload = {**full_payload(), "prompts": {"weekend": "  回答  "}}
    data = validate_profile_payload(payload, partial=False)
    assert data.prompts == {"weekend": "回答"}


def test_version_unsupported():
    payload = {**full_payload(), "questionnaire_version": "v2"}
    with pytest.raises(ProfileValidationError) as exc:
        validate_profile_payload(payload, partial=False)
    assert _codes(exc)["questionnaire_version"] == "QUESTIONNAIRE_VERSION_UNSUPPORTED"


def test_payload_too_large():
    with pytest.raises(PayloadTooLargeError):
        validate_profile_payload({"hard_answers": {"x": "a" * 17000}})


def test_patch_keeps_omitted_and_merges_answers():
    existing = ProfileData(
        hard_answers={"smoke": "yes"},
        soft_answers={"clean": 5},
        red_lines=["smoke"],
        red_lines_confirmed=True,
        tags=["夜猫子"],
        prompts={"weekend": "旧回答"},
    )
    data = validate_profile_payload(
        {"hard_answers": {"smoke": "no"}},
        partial=True,
        existing=existing,
    )
    assert data.hard_answers == {"smoke": "no"}
    assert data.soft_answers == {"clean": 5}
    assert data.red_lines == ["smoke"]
    assert data.tags == ["夜猫子"]
    assert data.prompts == {"weekend": "旧回答"}
    assert data.red_lines_confirmed is True


def test_patch_replaces_lists():
    existing = ProfileData(
        red_lines=["smoke"],
        red_lines_confirmed=True,
        tags=["夜猫子"],
        prompts={"weekend": "旧回答"},
    )
    data = validate_profile_payload(
        {"tags": ["早睡早起"], "prompts": {"vibe": "新回答"}},
        partial=True,
        existing=existing,
    )
    assert data.tags == ["早睡早起"]
    assert data.prompts == {"vibe": "新回答"}


def test_patch_changed_red_lines_resets_confirmation():
    existing = ProfileData(red_lines=["smoke"], red_lines_confirmed=True)
    data = validate_profile_payload(
        {"red_lines": ["pet"]},
        partial=True,
        existing=existing,
    )
    assert data.red_lines == ["pet"]
    assert data.red_lines_confirmed is False


def test_patch_changed_red_lines_with_explicit_true_keeps_confirmation():
    existing = ProfileData(red_lines=["smoke"], red_lines_confirmed=False)
    data = validate_profile_payload(
        {"red_lines": ["pet"], "red_lines_confirmed": True},
        partial=True,
        existing=existing,
    )
    assert data.red_lines_confirmed is True


def test_patch_explicit_false_resets_confirmation():
    existing = ProfileData(red_lines=["smoke"], red_lines_confirmed=True)
    data = validate_profile_payload(
        {"red_lines_confirmed": False},
        partial=True,
        existing=existing,
    )
    assert data.red_lines_confirmed is False


def test_patch_unchanged_red_lines_keeps_confirmation():
    existing = ProfileData(red_lines=["smoke"], red_lines_confirmed=True)
    data = validate_profile_payload(
        {"red_lines": ["smoke"]},
        partial=True,
        existing=existing,
    )
    assert data.red_lines_confirmed is True
