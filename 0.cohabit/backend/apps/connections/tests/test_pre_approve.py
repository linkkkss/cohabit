"""发起人预先确认 + 对方一键成立（docs/02 §3.5.5）。"""

from __future__ import annotations

import pytest

from apps.adminops.models import AuditLog
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.rooms.models import Room

from .helpers import (
    auth_client,
    body,
    error_code,
    make_connection,
    open_window,
    pair,
)

pytestmark = pytest.mark.django_db


def _pending() -> tuple:
    actor, target = pair()
    open_window()
    row = make_connection(initiator=actor, target=target)
    return actor, target, row


def test_pre_approve_marks_initiator_confirm():
    actor, _, row = _pending()

    response = auth_client(actor).post(f"/api/connections/{row.pk}/pre-approve")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "PENDING"
    assert payload["initiator_pre_approved"] is True
    assert payload["initiator_confirm_at"] is not None
    assert payload["actions"]["can_pre_approve"] is False
    row.refresh_from_db()
    assert row.status == ConnectionRequest.Status.PENDING
    assert row.initiator_confirm_at is not None
    audit = AuditLog.objects.get(action="CONNECTION_PRE_APPROVED")
    assert audit.meta["status"] == "PENDING"
    assert Notification.objects.count() == 0


def test_pre_approve_is_idempotent():
    actor, _, row = _pending()
    client = auth_client(actor)
    client.post(f"/api/connections/{row.pk}/pre-approve")

    response = client.post(f"/api/connections/{row.pk}/pre-approve")

    assert response.status_code == 200
    assert AuditLog.objects.filter(action="CONNECTION_PRE_APPROVED").count() == 1


def test_pre_approve_only_for_initiator():
    _, target, row = _pending()

    response = auth_client(target).post(f"/api/connections/{row.pk}/pre-approve")

    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_pre_approve_after_accept_is_invalid_state():
    actor, target, row = _pending()
    auth_client(target).post(f"/api/connections/{row.pk}/accept")

    response = auth_client(actor).post(f"/api/connections/{row.pk}/pre-approve")

    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"


def test_accept_after_pre_approve_establishes_room():
    actor, target, row = _pending()
    auth_client(actor).post(f"/api/connections/{row.pk}/pre-approve")

    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "CONFIRMED"
    assert payload["room"] is not None
    row.refresh_from_db()
    assert row.status == ConnectionRequest.Status.CONFIRMED
    assert row.initiator_confirm_at is not None
    assert row.target_confirm_at is not None
    assert Room.objects.count() == 1


def test_summary_exposes_last_active_and_close_reason():
    _, target, row = _pending()

    item = body(auth_client(target).get("/api/connections"))["results"][0]

    assert item["id"] == row.pk
    assert item["initiator_last_active_at"] is None
    assert item["target_last_active_at"] is None
    assert item["initiator_pre_approved"] is False
    assert item["close_reason"] == ""


def test_target_accept_without_pre_approve_keeps_two_step():
    _, target, row = _pending()

    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")

    assert response.status_code == 200
    assert body(response)["status"] == "CONTACT_SHARED"
