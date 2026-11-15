"""匹配 API 测试（docs/04 §4.2：候选列表、详情、评分、错误映射）。"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.adminops.models import Block
from apps.matching.throttling import SCORE_LIMIT
from apps.profiles.services import save_profile

from apps.profiles.tests.helpers import full_payload, full_tags

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_user(*, uid: str, email: str, gender: str = "MALE", major: str = "软件工程", college: str = "计算机学院", nickname: str = "同学") -> User:
    return User.objects.create_user(
        uid=uid,
        email=email,
        password="Xk9#mQ2!zR7",
        nickname=nickname,
        gender=gender,
        grade=2,
        college=college,
        major=major,
    )


def complete(user: User, *, tags: list[str] | None = None) -> None:
    payload = full_payload()
    payload["tags"] = tags if tags is not None else full_tags()
    save_profile(user, payload)


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_match_requires_authentication():
    response = APIClient().get("/api/match")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_match_requires_complete_profile():
    seeker = make_user(uid="0000000001", email="seeker@stu.edu.cn")
    response = auth_client(seeker).get("/api/match")
    assert response.status_code == 403
    assert response.json()["code"] == "PROFILE_INCOMPLETE"


def test_match_list_sorted_and_complete_payload():
    seeker = make_user(uid="0000000002", email="s2@stu.edu.cn")
    complete(seeker)
    first = make_user(uid="0000000003", email="t3@stu.edu.cn", nickname="甲")
    second = make_user(uid="0000000004", email="t4@stu.edu.cn", nickname="乙")
    complete(first)
    complete(second)

    body = auth_client(seeker).get("/api/match").json()
    assert body["count"] == 2
    scores = [item["score"] for item in body["results"]]
    assert scores == sorted(scores, reverse=True)
    item = body["results"][0]
    assert {"target", "score", "base", "tag_bonus", "red_penalty", "dims", "reasons"} <= set(
        item
    )
    assert set(item["dims"]) == {"a", "b", "dim_score"}
    assert len(item["dims"]["dim_score"]) == 6
    assert item["reasons"]


def test_match_filters_and_pagination():
    seeker = make_user(uid="0000000005", email="s5@stu.edu.cn")
    complete(seeker)
    same = make_user(uid="0000000006", email="t6@stu.edu.cn", major="软件工程")
    other = make_user(uid="0000000007", email="t7@stu.edu.cn", major="计算机科学")
    complete(same)
    complete(other)

    client = auth_client(seeker)
    major_filtered = client.get("/api/match", {"major": "软件工程"}).json()
    assert [item["target"]["uid"] for item in major_filtered["results"]] == [same.uid]

    tag_filtered = client.get("/api/match", {"tags": "zzz-not-exist"})
    assert tag_filtered.status_code == 200
    assert tag_filtered.json()["count"] == 0

    bad_min = client.get("/api/match", {"min_score": "101"})
    assert bad_min.status_code == 400
    assert "min_score" in bad_min.json()["detail"]["fields"]

    paged = client.get("/api/match", {"page_size": 1}).json()
    assert paged["count"] == 2 and len(paged["results"]) == 1
    truncated = client.get("/api/match", {"page_size": 500})
    assert truncated.status_code == 200


def test_match_detail_and_score_endpoints():
    seeker = make_user(uid="0000000008", email="s8@stu.edu.cn")
    complete(seeker)
    target = make_user(uid="0000000009", email="t9@stu.edu.cn")
    complete(target)

    client = auth_client(seeker)
    detail = client.get(f"/api/match/{target.uid}")
    assert detail.status_code == 200
    assert detail.json()["target"]["uid"] == target.uid

    scored = client.post(f"/api/match/{target.uid}/score", {}, format="json")
    assert scored.status_code == 200
    assert scored.json()["target"]["uid"] == target.uid


def test_match_score_rate_limit(monkeypatch):
    seeker = make_user(uid="0000000010", email="s10@stu.edu.cn")
    complete(seeker)
    target = make_user(uid="0000000011", email="t11@stu.edu.cn")
    complete(target)

    monkeypatch.setattr("apps.matching.throttling.SCORE_LIMIT", 1)
    client = auth_client(seeker)
    assert client.post(f"/api/match/{target.uid}/score", {}, format="json").status_code == 200
    limited = client.post(f"/api/match/{target.uid}/score", {}, format="json")
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"
    assert limited["Retry-After"]
    assert SCORE_LIMIT > 1  # 默认值保持 60/h


def test_match_detail_error_mapping():
    seeker = make_user(uid="0000000012", email="s12@stu.edu.cn")
    complete(seeker)
    incomplete = make_user(uid="0000000013", email="t13@stu.edu.cn")
    other_college = make_user(
        uid="0000000014", email="t14@stu.edu.cn", college="外国语学院"
    )
    other_gender = make_user(uid="0000000015", email="t15@stu.edu.cn", gender="FEMALE")
    blocked = make_user(uid="0000000016", email="t16@stu.edu.cn")
    complete(blocked)
    Block.objects.create(blocker=seeker, blocked=blocked)

    client = auth_client(seeker)
    cases = [
        (incomplete.uid, 409, "TARGET_PROFILE_INCOMPLETE"),
        (other_college.uid, 404, "PROFILE_NOT_FOUND"),
        (other_gender.uid, 404, "PROFILE_NOT_FOUND"),
        ("9999999999", 404, "PROFILE_NOT_FOUND"),
        (blocked.uid, 403, "BLOCKED"),
        (seeker.uid, 400, "INVALID_TARGET"),
    ]
    for uid, status, code in cases:
        response = client.get(f"/api/match/{uid}")
        assert response.status_code == status, (uid, response.content)
        assert response.json()["code"] == code
