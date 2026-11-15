"""画像服务中的纯计算部分（不落库）。"""

from __future__ import annotations

from types import SimpleNamespace

from apps.profiles.services import (
    _compute,
    profile_is_complete,
    profile_questionnaire,
)
from apps.profiles.tests.helpers import (
    full_hard,
    full_prompts,
    full_soft,
    full_tags,
    make_user,
)
from apps.profiles.validation import ProfileData


def test_compute_full_profile():
    profile = SimpleNamespace(user=make_user())
    data = ProfileData(
        hard_answers=full_hard(),
        soft_answers=full_soft(5),
        red_lines=["smoke"],
        red_lines_confirmed=True,
        tags=full_tags(),
        prompts=full_prompts(),
    )
    computed = _compute(profile, data)
    assert computed["completeness"] == 100
    assert computed["dims"]["clean"] == 100
    assert computed["dims"]["sleep"] == 100


def test_profile_is_complete():
    assert profile_is_complete(SimpleNamespace(completeness=100))
    assert not profile_is_complete(SimpleNamespace(completeness=99))
    assert not profile_is_complete(None)


def test_profile_questionnaire_shape():
    profile = SimpleNamespace(
        hard_answers={"smoke": "no"},
        soft_answers={"clean": 3},
        red_lines=[],
        red_lines_confirmed=False,
        tags=[],
        prompts={},
        dims={"clean": 50},
        completeness=30,
        questionnaire_version="v1",
    )
    payload = profile_questionnaire(profile)
    assert payload["hard_answers"] == {"smoke": "no"}
    assert payload["completeness"] == 30
    assert payload["questionnaire_version"] == "v1"
    assert set(payload) == {
        "hard_answers",
        "soft_answers",
        "red_lines",
        "red_lines_confirmed",
        "tags",
        "prompts",
        "dims",
        "completeness",
        "questionnaire_version",
    }
