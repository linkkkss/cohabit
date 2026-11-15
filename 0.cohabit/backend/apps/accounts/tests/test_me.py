"""PUT /api/me 基础资料修改（docs/04 §4.1、docs/06 A-04）。"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "Xk9#mQ2!zR7"


def make_user(**overrides) -> User:
    data = {
        "uid": "0000000101",
        "email": "me@stu.edu.cn",
        "password": PASSWORD,
        "nickname": "小满",
        "gender": "FEMALE",
        "grade": 2,
        "college": "计算机学院",
        "major": "软件工程",
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_put_me_updates_writable_fields():
    user = make_user()
    response = auth_client(user).put(
        "/api/me",
        {"nickname": "  新昵称  ", "grade": 4, "major": "人工智能"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["nickname"] == "新昵称"
    assert body["grade"] == 4
    assert body["major"] == "人工智能"
    assert body["college"] == "计算机学院"  # 未提供则不变
    assert body["gender"] == "FEMALE"
    assert "email" not in body and "contact" not in body
    assert set(body) == {
        "uid",
        "nickname",
        "avatar_key",
        "gender",
        "college",
        "major",
        "grade",
        "role",
        "status",
        "profile_completeness",
        "questionnaire_version",
        "room",
        "unread_count",
    }

    user.refresh_from_db()
    assert (user.nickname, user.grade, user.major) == ("新昵称", 4, "人工智能")


def test_put_me_rejects_gender_change():
    user = make_user()
    response = auth_client(user).put(
        "/api/me", {"gender": "MALE", "nickname": "改名"}, format="json"
    )
    assert response.status_code == 403
    assert response.json()["code"] == "GENDER_IMMUTABLE"
    user.refresh_from_db()
    assert user.gender == "FEMALE"
    assert user.nickname == "小满"


@pytest.mark.parametrize("payload", [{"grade": 0}, {"grade": 9}, {"nickname": "  "}])
def test_put_me_rejects_invalid_values(payload):
    user = make_user()
    response = auth_client(user).put("/api/me", payload, format="json")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body["detail"]["fields"]) == set(payload)


def test_put_me_requires_authentication():
    response = APIClient().put("/api/me", {"nickname": "x"}, format="json")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_put_me_rejects_protected_fields_and_keeps_them():
    user = make_user()
    response = auth_client(user).put(
        "/api/me",
        {"email": "hack@stu.edu.cn", "uid": "1234567890", "role": "ADMIN"},
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body["detail"]["fields"]) == {"email", "uid", "role"}

    user.refresh_from_db()
    assert user.email == "me@stu.edu.cn"
    assert user.uid == "0000000101"
    assert user.role == User.Role.STUDENT


def test_put_me_rejects_unknown_field():
    user = make_user()
    response = auth_client(user).put("/api/me", {"unknown_key": 1}, format="json")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "unknown_key" in body["detail"]["fields"]


def test_put_me_empty_payload_is_noop():
    user = make_user()
    response = auth_client(user).put("/api/me", {}, format="json")
    assert response.status_code == 200
    assert response.json()["nickname"] == "小满"
