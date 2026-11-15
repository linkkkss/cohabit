"""候选硬过滤（docs/03 §8.2）与排序键（纯函数部分）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from apps.accounts.models import User
from apps.matching.candidates import is_candidate
from apps.matching.services import _sort_key


def make_user(pk: int = 2, **overrides):
    values = {
        "pk": pk,
        "uid": f"000000000{pk}",
        "college": "计算机学院",
        "gender": "MALE",
        "status": User.Status.ACTIVE,
        "role": User.Role.STUDENT,
        "is_active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_candidate_accepts_eligible_user():
    seeker = make_user(pk=1)
    candidate = make_user()
    assert is_candidate(
        seeker,
        candidate,
        candidate_profile=SimpleNamespace(completeness=100),
    )


def test_candidate_rejects_self():
    seeker = make_user(pk=1)
    assert not is_candidate(
        seeker,
        seeker,
        candidate_profile=SimpleNamespace(completeness=100),
    )


def test_candidate_rejects_wrong_college_or_gender():
    seeker = make_user(pk=1)
    profile = SimpleNamespace(completeness=100)
    assert not is_candidate(
        seeker,
        make_user(college="外国语学院"),
        candidate_profile=profile,
    )
    assert not is_candidate(
        seeker,
        make_user(gender="FEMALE"),
        candidate_profile=profile,
    )


def test_candidate_rejects_inactive_or_admin():
    seeker = make_user(pk=1)
    profile = SimpleNamespace(completeness=100)
    assert not is_candidate(
        seeker,
        make_user(status=User.Status.DISABLED),
        candidate_profile=profile,
    )
    assert not is_candidate(
        seeker,
        make_user(role=User.Role.ADMIN),
        candidate_profile=profile,
    )
    assert not is_candidate(
        seeker,
        make_user(is_active=False),
        candidate_profile=profile,
    )


def test_candidate_rejects_incomplete_profile():
    seeker = make_user(pk=1)
    assert not is_candidate(
        seeker,
        make_user(),
        candidate_profile=SimpleNamespace(completeness=99),
    )
    assert not is_candidate(seeker, make_user(), candidate_profile=None)


def test_candidate_rejects_room_block_inflight():
    seeker = make_user(pk=1)
    profile = SimpleNamespace(completeness=100)
    assert not is_candidate(
        seeker,
        make_user(),
        candidate_profile=profile,
        has_active_room=True,
    )
    assert not is_candidate(
        seeker,
        make_user(),
        candidate_profile=profile,
        blocked=True,
    )
    assert not is_candidate(
        seeker,
        make_user(),
        candidate_profile=profile,
        inflight=True,
    )


def test_sort_key_orders_by_score_then_completeness_then_recency():
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)

    def item(uid, score, completeness, updated_at):
        return {
            "user": SimpleNamespace(uid=uid),
            "profile": SimpleNamespace(
                completeness=completeness,
                updated_at=updated_at,
            ),
            "match": {"score": score},
        }

    items = [
        item("0000000002", 90, 100, now - timedelta(hours=1)),
        item("0000000001", 95, 100, now),
        item("0000000003", 90, 100, now),
        item("0000000004", 90, 90, now),
    ]
    ordered = sorted(items, key=_sort_key)
    assert [entry["user"].uid for entry in ordered] == [
        "0000000001",
        "0000000003",
        "0000000002",
        "0000000004",
    ]
