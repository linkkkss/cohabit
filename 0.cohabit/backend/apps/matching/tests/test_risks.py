"""候选人风险摘要（apps.matching.risks + MatchScore.risks）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.accounts.models import User
from apps.matching.risks import risk_items
from apps.profiles.services import save_profile
from apps.profiles.tests.helpers import full_payload, full_tags

pytestmark = pytest.mark.django_db


def profile(**hard) -> SimpleNamespace:
    answers = {"sleep_time": "before23"}
    answers.update(hard)
    return SimpleNamespace(hard_answers=answers, soft_answers={})


def match(clean_dim: int = 100, conflicts: list | None = None) -> dict:
    return {
        "score": 80,
        "dims": {"a": {}, "b": {}, "dim_score": {"clean": clean_dim}},
        "conflicts": conflicts or [],
    }


def codes(items: list[dict]) -> list[str]:
    return [item["code"] for item in items]


def test_no_risk_when_similar():
    items = risk_items(profile(sleep_time="23_00"), profile(sleep_time="00_01"), match())

    assert items == []


def test_sleep_gap_uses_circular_hours():
    items = risk_items(
        profile(sleep_time="before23"),  # 22:00
        profile(sleep_time="after01"),  # 02:00
        match(),
    )

    assert codes(items) == ["sleep_gap"]
    assert items[0]["text"] == "作息相差 4 小时"


def test_sleep_gap_below_threshold_is_quiet():
    items = risk_items(
        profile(sleep_time="23_00"),  # 23:30
        profile(sleep_time="00_01"),  # 00:30
        match(),
    )

    assert items == []


def test_clean_gap_reports_large_difference():
    items = risk_items(profile(), profile(), match(clean_dim=60))

    assert codes(items) == ["clean_gap"]
    assert items[0]["text"] == "整洁度差异较大"


def test_red_line_first_and_counted():
    items = risk_items(
        profile(sleep_time="before23"),
        profile(sleep_time="after01"),
        match(conflicts=[{"owner": "a"}, {"owner": "b"}]),
    )

    assert codes(items) == ["red_line", "sleep_gap"]
    assert items[0]["text"] == "存在 2 项红线冲突"


def test_missing_answers_are_silent():
    items = risk_items(SimpleNamespace(hard_answers={}), profile(), match())

    assert items == []


def make_user(*, uid: str, email: str, nickname: str) -> User:
    return User.objects.create_user(
        uid=uid,
        email=email,
        password=None,
        nickname=nickname,
        gender="MALE",
        grade=2,
        college="计算机学院",
        major="软件工程",
    )


def complete(user: User, *, sleep_time: str) -> None:
    payload = full_payload()
    payload["hard_answers"]["sleep_time"] = sleep_time
    payload["tags"] = full_tags()
    save_profile(user, payload)


def test_match_payload_carries_risks_and_last_active():
    from rest_framework.test import APIClient

    seeker = make_user(uid="0000000101", email="r1@example.com", nickname="甲")
    target = make_user(uid="0000000102", email="r2@example.com", nickname="乙")
    complete(seeker, sleep_time="23_00")
    complete(target, sleep_time="after01")

    client = APIClient()
    client.force_authenticate(user=seeker)
    item = client.get("/api/match").json()["results"][0]

    assert item["target"]["uid"] == target.uid
    assert "last_active_at" in item["target"]
    assert [risk["code"] for risk in item["risks"]] == ["sleep_gap"]
    assert item["risks"][0]["text"] == "作息相差 2.5 小时"

