"""邀请码模型与注册占用（docs/03 §1.3.4、docs/04 §2.2）。"""

from __future__ import annotations

import datetime as dt
import threading

import pytest
from django.db import connections
from django.test import Client as DjangoTestClient
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.exceptions import ApiError
from apps.accounts.models import (
    INVITE_CODE_ALPHABET,
    InviteCode,
    User,
    generate_invite_code,
)

pytestmark = pytest.mark.django_db

PASSWORD = "Xk9#mQ2!zR7"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "email": "lily@stu.edu.cn",
        "code": "123456",
        "password": PASSWORD,
        "nickname": "小满",
        "gender": "FEMALE",
        "grade": 2,
        "college": "计算机学院",
        "major": "软件工程",
    }
    data.update(overrides)
    return data


def test_generated_code_is_unambiguous():
    code = generate_invite_code()

    assert len(code) == 10
    assert set(code) <= set(INVITE_CODE_ALPHABET)
    assert not set(code) & set("0O1I")


def test_documented_code_cohb2026_passes_validation_and_registers(client):
    invite = InviteCode(code="COHAB2026", max_uses=1)
    invite.full_clean()  # 含 0 的文档固定码必须通过校验（Lead 裁决）
    invite.save()

    response = client.post(
        "/api/auth/register", payload(invite_code="COHAB2026"), format="json"
    )

    assert response.status_code == 201
    invite.refresh_from_db()
    assert invite.used_count == 1


def test_is_usable_covers_all_rejection_reasons():
    now = timezone.now()

    assert InviteCode(code="COHAB2026", max_uses=1).is_usable(now)
    assert InviteCode(code="ANY23456", max_uses=0, used_count=99).is_usable(now)
    assert not InviteCode(code="OFF23456", is_active=False).is_usable(now)
    assert not InviteCode(code="EXPIRED2", expires_at=now - dt.timedelta(seconds=1)).is_usable(
        now
    )
    assert not InviteCode(code="USED1234", max_uses=1, used_count=1).is_usable(now)


def test_register_with_valid_code_increments_used_count(client):
    invite = InviteCode.objects.create(code="COHAB2026", max_uses=2)

    response = client.post(
        "/api/auth/register", payload(invite_code="cohab2026"), format="json"
    )

    assert response.status_code == 201
    invite.refresh_from_db()
    assert invite.used_count == 1
    assert User.objects.filter(email="lily@stu.edu.cn").exists()


@pytest.mark.parametrize(
    "invite_kwargs",
    [
        {"is_active": False},
        {"expires_at": timezone.now() - dt.timedelta(minutes=1)},
        {"max_uses": 1, "used_count": 1},
    ],
)
def test_register_rejects_unusable_code(client, invite_kwargs):
    existing = InviteCode.objects.create(code="COHAB2026", **invite_kwargs)

    response = client.post(
        "/api/auth/register", payload(invite_code="COHAB2026"), format="json"
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVITE_INVALID"
    assert User.objects.count() == 0
    existing.refresh_from_db()
    assert existing.used_count == invite_kwargs.get("used_count", 0)


def test_register_rejects_unknown_code(client):
    response = client.post("/api/auth/register", payload(invite_code="ZZZZ9999"), format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "INVITE_INVALID"


def test_register_requires_code_when_switch_on(monkeypatch, client):
    monkeypatch.setenv("INVITE_REQUIRED", "true")

    response = client.post("/api/auth/register", payload(), format="json")

    assert response.status_code == 403
    assert response.json()["code"] == "INVITE_REQUIRED"


def test_register_without_code_when_switch_off(client):
    response = client.post("/api/auth/register", payload(), format="json")

    assert response.status_code == 201


def test_register_with_code_switch_off_still_validates(client):
    response = client.post("/api/auth/register", payload(invite_code="ZZZZ9999"), format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "INVITE_INVALID"


def test_admin_can_create_invite_code_with_generated_code():
    admin = User.objects.create_superuser(
        email="admin@stu.edu.cn",
        password=PASSWORD,
        nickname="管理员",
        gender=User.Gender.MALE,
        college="计算机学院",
    )
    client = DjangoTestClient()
    client.force_login(admin)

    page = client.get("/admin/accounts/invitecode/add/")
    assert page.status_code == 200

    response = client.post(
        "/admin/accounts/invitecode/add/",
        {
            "code": "",
            "note": "内测",
            "max_uses": "0",
            "expires_at_0": "",
            "expires_at_1": "",
            "is_active": "on",
            "created_by": "",
        },
    )

    assert response.status_code == 302
    invite = InviteCode.objects.get()
    assert len(invite.code) == 10
    assert set(invite.code) <= set(INVITE_CODE_ALPHABET)
    assert invite.created_by == admin
    assert invite.note == "内测"
    assert invite.max_uses == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_registration_does_not_oversell():
    InviteCode.objects.create(code="RACE2026", max_uses=1)
    barrier = threading.Barrier(2)
    results: list[str] = []
    results_lock = threading.Lock()

    def worker(index: int) -> None:
        outcome = "error"
        try:
            barrier.wait(timeout=10)
            services.register_user(
                payload(email=f"race{index}@stu.edu.cn", invite_code="RACE2026"),
                client_ip=f"10.0.0.{index}",
            )
            outcome = "ok"
        except ApiError as exc:
            outcome = exc.error_code
        finally:
            connections.close_all()
            with results_lock:
                results.append(outcome)

    threads = [threading.Thread(target=worker, args=(index,)) for index in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert results.count("ok") == 1, results
    assert results.count("INVITE_INVALID") == 1, results
    invite = InviteCode.objects.get(code="RACE2026")
    assert invite.used_count == 1
    assert User.objects.count() == 1
