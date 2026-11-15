"""认证 API 端到端测试（docs/04 §2/§4.1；契约路径无尾斜杠）。"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts import conf

User = get_user_model()
PASSWORD = "Xk9#mQ2!zR7"
AVATAR_KEYS = {f"avatar-{index:02d}" for index in range(1, 7)}

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def register_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": "Lily@Stu.edu.cn",
        "code": "123456",
        "password": PASSWORD,
        "nickname": "小满",
        "gender": "FEMALE",
        "grade": 2,
        "college": "计算机学院",
        "major": "软件工程",
    }
    payload.update(overrides)
    return payload


def register(client: APIClient, **overrides: object):
    return client.post("/api/auth/register", register_payload(**overrides), format="json")


def cookie_of(response) -> dict[str, object]:
    cookie = response.cookies[conf.COOKIE_NAME]
    return {
        "value": cookie.value,
        "httponly": cookie["httponly"],
        "samesite": cookie["samesite"],
        "path": cookie["path"],
        "max-age": cookie["max-age"],
        "secure": cookie["secure"],
    }


def test_send_code_returns_dev_code_in_debug(client):
    response = client.post("/api/auth/send-code", {"email": "a@stu.edu.cn"}, format="json")

    assert response.status_code == 200
    assert response.json()["dev_code"] == conf.DEV_VERIFICATION_CODE


def test_send_code_is_rate_limited(client):
    assert client.post("/api/auth/send-code", {"email": "a@stu.edu.cn"}).status_code == 200
    response = client.post("/api/auth/send-code", {"email": "a@stu.edu.cn"})

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
    assert int(response["Retry-After"]) >= 1


def test_register_creates_user_and_sets_cookie(client):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["expires_in"] == 1800
    assert re.fullmatch(r"\d{10}", body["user"]["uid"])
    assert body["user"]["avatar_key"] in AVATAR_KEYS
    assert body["user"]["role"] == "STUDENT"
    assert body["user"]["status"] == "ACTIVE"
    assert body["user"]["questionnaire_version"] == "v1"
    assert body["user"]["room"] is None
    assert "email" not in body["user"]
    assert "contact" not in response.content.decode()

    user = User.objects.get()
    assert user.email == "lily@stu.edu.cn"
    assert user.uid == body["user"]["uid"]
    assert user.check_password(PASSWORD)

    cookie = cookie_of(response)
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    assert cookie["path"] == "/api/auth/"
    assert cookie["max-age"] == 604800
    assert not cookie["secure"]  # DEBUG 下不带 Secure


def test_register_rejects_wrong_code(client):
    response = register(client, code="000000")

    assert response.status_code == 400
    assert response.json()["code"] == "CODE_INVALID"


def test_register_reports_expired_code(client):
    email = "lily@stu.edu.cn"
    cache.set(f"auth:code-seen:{email}", True, timeout=60)

    response = register(client, code="654321")

    assert response.status_code == 400
    assert response.json()["code"] == "CODE_EXPIRED"


def test_register_rejects_duplicate_email_case_insensitive(client):
    assert register(client).status_code == 201

    response = register(client, email="LILY@stu.edu.cn")

    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_TAKEN"
    assert User.objects.count() == 1


def test_register_validates_fields(client):
    response = register(client, password="short")

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "password" in body["detail"]["fields"]


def test_login_success_and_wrong_password(client):
    assert register(client).status_code == 201
    User.objects.filter(email="lily@stu.edu.cn").update(is_active=True)

    ok = client.post(
        "/api/auth/login",
        {"email": "LILY@stu.edu.cn", "password": PASSWORD},
        format="json",
    )
    assert ok.status_code == 200
    assert ok.json()["access"]
    assert ok.json()["user"]["uid"]
    assert cookie_of(ok)["path"] == "/api/auth/"

    wrong = client.post(
        "/api/auth/login",
        {"email": "lily@stu.edu.cn", "password": "wrong-password"},
        format="json",
    )
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "INVALID_CREDENTIALS"


def test_login_disabled_account_returns_403(client):
    assert register(client).status_code == 201
    User.objects.filter(email="lily@stu.edu.cn").update(status=User.Status.DISABLED)

    response = client.post(
        "/api/auth/login",
        {"email": "lily@stu.edu.cn", "password": PASSWORD},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


def test_refresh_rotates_and_blacklists_old_token(client):
    original = cookie_of(register(client))["value"]

    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access"]
    assert refreshed.json()["expires_in"] == 1800
    rotated = cookie_of(refreshed)["value"]
    assert rotated != original

    replay = APIClient()
    replay.cookies[conf.COOKIE_NAME] = original
    reused = replay.post("/api/auth/refresh")
    assert reused.status_code == 401
    assert reused.json()["code"] == "TOKEN_INVALID"


def test_refresh_requires_cookie(client):
    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_refresh_rejects_foreign_origin(client):
    client.cookies[conf.COOKIE_NAME] = cookie_of(register(client))["value"]

    response = client.post("/api/auth/refresh", HTTP_ORIGIN="https://evil.example")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_logout_clears_cookie_and_blacklists(client):
    cookie = cookie_of(register(client))

    first = client.post("/api/auth/logout")
    assert first.status_code == 204
    cleared = cookie_of(first)
    assert cleared["max-age"] == 0

    second = client.post("/api/auth/logout")
    assert second.status_code == 204

    replay = APIClient()
    replay.cookies[conf.COOKIE_NAME] = cookie["value"]
    assert replay.post("/api/auth/refresh").status_code == 401


def test_production_mode_hides_dev_code(settings, client):
    settings.DEBUG = False

    response = client.post("/api/auth/send-code", {"email": "lily@stu.edu.cn"})
    assert response.status_code == 204

    code = cache.get("auth:code:lily@stu.edu.cn")
    assert isinstance(code, str) and re.fullmatch(r"\d{6}", code)

    rejected = register(client, code=conf.DEV_VERIFICATION_CODE)
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "CODE_INVALID"

    accepted = register(client, code=code)
    assert accepted.status_code == 201
    assert cookie_of(accepted)["secure"] is True


def test_me_requires_authentication(client):
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_me_returns_contract_shape(client):
    access = register(client).json()["access"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = client.get("/api/me")

    assert response.status_code == 200
    body = response.json()
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
    assert "email" not in response.content.decode()
    assert "contact" not in response.content.decode()


def test_me_rejects_expired_or_bogus_token(client):
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"
