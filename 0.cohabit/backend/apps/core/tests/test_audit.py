"""``write_audit`` 单元测试（docs/02 §9、docs/03 §1.8.3）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.adminops.models import AuditLog
from apps.core.audit import normalize_action, normalize_target_type, write_audit
from apps.core.privacy import PayloadNotPublicError

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(
        uid="1000000001",
        email="alice@example.com",
        password="Xk9#mQ2!zR7",
        nickname="小满",
        gender="MALE",
        grade=2,
        college="计算机学院",
    )


@pytest.fixture
def other_user():
    return User.objects.create_user(
        uid="1000000002",
        email="bob@example.com",
        password="Xk9#mQ2!zR7",
        nickname="小林",
        gender="MALE",
        grade=2,
        college="计算机学院",
    )


def test_write_audit_persists_fields(user):
    row = write_audit(
        "CONNECTION_CREATED",
        "connection",
        42,
        actor=user,
        meta={"request_type": "INVITE", "status": "PENDING"},
        request_id="req-abc-123",
    )

    row.refresh_from_db()
    assert row.actor_id == user.pk
    assert row.action == "CONNECTION_CREATED"
    assert row.target_type == AuditLog.TargetType.CONNECTION
    assert row.target_id == 42
    assert row.meta == {"request_type": "INVITE", "status": "PENDING"}
    assert row.request_id == "req-abc-123"
    assert row.created_at is not None


def test_system_audit_has_no_actor_and_empty_defaults():
    row = write_audit("WINDOW_CREATED", "time_window", 7)

    row.refresh_from_db()
    assert row.actor_id is None
    assert row.target_type == AuditLog.TargetType.WINDOW
    assert row.meta == {}
    assert row.request_id == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (AuditLog.TargetType.CONNECTION, "CONNECTION"),
        (AuditLog.TargetType.ROOM, "ROOM"),
        (AuditLog.TargetType.USER, "USER"),
        ("connection", "CONNECTION"),
        ("room", "ROOM"),
        ("room_member", "ROOM"),
        ("transfer", "TRANSFER"),
        ("time_window", "WINDOW"),
        ("window", "WINDOW"),
        ("user", "USER"),
        ("report", "REPORT"),
        ("invite_code", "INVITE"),
        ("notification", "NOTIFICATION"),
    ],
)
def test_normalize_target_type(value, expected):
    assert normalize_target_type(value) == expected


def test_normalize_target_type_rejects_unknown():
    with pytest.raises(ValueError, match="未知的 target_type"):
        normalize_target_type("planet")


def test_action_is_normalized_to_upper_snake_case():
    assert normalize_action("room_created") == "ROOM_CREATED"
    assert normalize_action("ROOM_LOCKED") == "ROOM_LOCKED"


@pytest.mark.parametrize("action", ["", "ROOM CREATED", "room-created", "1ROOM", "A" * 51])
def test_normalize_action_rejects_invalid(action):
    with pytest.raises(ValueError):
        normalize_action(action)


def test_target_id_accepts_model_instance(user, other_user):
    row = write_audit("USER_DISABLED", "user", other_user, actor=user)

    assert row.target_id == other_user.pk
    assert row.actor_id == user.pk


def test_actor_accepts_primary_key(user):
    row = write_audit("USER_DISABLED", "user", user.pk, actor=user.pk)

    assert row.actor_id == user.pk


@pytest.mark.parametrize(
    "meta",
    [
        {"email": "alice@example.com"},
        {"contact_phone": "13800000000"},
        {"reply": {"qq": "123456"}},
        {"tokens": [{"refresh_token": "secret"}]},
        {"user_email": "alice@example.com"},
    ],
)
def test_write_audit_rejects_forbidden_meta(meta):
    with pytest.raises(PayloadNotPublicError):
        write_audit("REPORT_HANDLED", "report", 1, meta=meta)
    assert AuditLog.objects.count() == 0


def test_write_audit_rejects_non_dict_meta():
    with pytest.raises(ValueError, match="meta"):
        write_audit("REPORT_HANDLED", "report", 1, meta=["not", "a", "dict"])


def test_request_id_truncated_to_model_limit():
    row = write_audit("ROOM_CREATED", "room", 1, request_id="x" * 80)

    assert len(row.request_id) == 64


def test_audit_rolls_back_with_business_transaction(user):
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            write_audit("ROOM_CREATED", "room", 1, actor=user)
            raise RuntimeError("business failed")

    assert AuditLog.objects.count() == 0


def test_audit_created_at_is_recent():
    row = write_audit("ROOM_CREATED", "room", 1)

    assert timezone.now() - row.created_at < timedelta(seconds=30)
