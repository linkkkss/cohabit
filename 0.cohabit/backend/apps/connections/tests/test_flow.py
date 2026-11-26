"""accept / decline / cancel、列表与 contact 可见性（docs/02 §3.3–§3.8）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.adminops.models import AuditLog
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification

from .helpers import (
    auth_client,
    body,
    complete_profile,
    error_code,
    make_connection,
    make_contact,
    make_room,
    make_user,
    open_window,
    pair,
)

pytestmark = pytest.mark.django_db


def _pending(*, same_college: bool = True) -> tuple:
    actor, target = pair()
    open_window()
    row = make_connection(initiator=actor, target=target)
    return actor, target, row


def test_list_inbox_and_sent():
    actor, target, row = _pending()

    inbox = body(auth_client(target).get("/api/connections"))["results"]
    assert len(inbox) == 1
    assert inbox[0]["id"] == row.pk
    assert inbox[0]["direction"] == "inbox"
    assert "contact" not in inbox[0]
    assert "initiator_confirm_at" not in inbox[0]

    sent = body(auth_client(actor).get("/api/connections", {"role": "sent"}))["results"]
    assert [item["id"] for item in sent] == [row.pk]
    assert sent[0]["direction"] == "sent"

    alias = body(auth_client(actor).get("/api/connections", {"box": "outgoing"}))
    assert [item["id"] for item in alias["results"]] == [row.pk]


def test_list_filters_by_status():
    actor, target, row = _pending()
    other = make_user()
    complete_profile(other)
    make_connection(
        initiator=actor,
        target=other,
        status=ConnectionRequest.Status.CANCELLED,
        close_reason=ConnectionRequest.CloseReason.INITIATOR_CANCEL,
    )

    pending = body(
        auth_client(actor).get("/api/connections", {"role": "sent", "status": "PENDING"})
    )
    assert [item["id"] for item in pending["results"]] == [row.pk]

    cancelled = body(
        auth_client(actor).get(
            "/api/connections",
            {"role": "sent", "status": "CANCELLED,DECLINED"},
        )
    )
    assert len(cancelled["results"]) == 1


def test_list_requires_login():
    response = APIClient().get("/api/connections")
    assert response.status_code == 401
    assert error_code(response) == "AUTH_REQUIRED"


def test_detail_non_participant_returns_404():
    _, _, row = _pending()
    outsider = make_user()
    complete_profile(outsider)
    response = auth_client(outsider).get(f"/api/connections/{row.pk}")
    assert response.status_code == 404
    assert error_code(response) == "CONNECTION_NOT_FOUND"


def test_detail_pending_hides_contact():
    actor, target, row = _pending()
    make_contact(target)
    payload = body(auth_client(actor).get(f"/api/connections/{row.pk}"))
    assert payload["status"] == "PENDING"
    assert payload["contact"] == {}
    assert payload["actions"] == {
        "can_accept": False,
        "can_decline": False,
        "can_cancel": True,
        "can_confirm": False,
        "can_pre_approve": True,
        "can_view_contact": False,
    }


def test_accept_by_target_shares_contact():
    actor, target, row = _pending()
    make_contact(actor)

    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "CONTACT_SHARED"
    assert payload["contact"] == {
        "qq": "12345678",
        "wechat": "wx_abc",
        "unlocked": True,
    }
    assert payload["contact_shared_at"] is not None
    row.refresh_from_db()
    assert row.status == "CONTACT_SHARED"
    assert row.contact_shared_at is not None
    assert abs(row.expires_at - (timezone.now() + timedelta(days=7))) < timedelta(
        minutes=2
    )
    note = Notification.objects.get(
        user=actor, type=Notification.Type.CONTACT_SHARED
    )
    assert note.payload == {"connection_id": row.pk}
    audit = AuditLog.objects.get(action="CONNECTION_ACCEPTED")
    assert audit.meta == {"from": "PENDING", "to": "CONTACT_SHARED"}
    assert audit.actor_id == target.pk


def test_accept_by_initiator_forbidden():
    actor, _, row = _pending()
    response = auth_client(actor).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_accept_twice_returns_invalid_state():
    _, target, row = _pending()
    assert auth_client(target).post(f"/api/connections/{row.pk}/accept").status_code == 200
    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"


def test_accept_closed_request_returns_request_closed():
    _, target, row = _pending()
    ConnectionRequest.objects.filter(pk=row.pk).update(
        status=ConnectionRequest.Status.DECLINED,
        close_reason=ConnectionRequest.CloseReason.DECLINED,
    )
    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 409
    assert error_code(response) == "REQUEST_CLOSED"


def test_accept_lazy_expires_request():
    actor, target, row = _pending()
    ConnectionRequest.objects.filter(pk=row.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")

    assert response.status_code == 409
    assert error_code(response) == "REQUEST_EXPIRED"
    row.refresh_from_db()
    assert row.status == "EXPIRED"
    assert row.close_reason == "TIMEOUT"
    for user in (actor, target):
        note = Notification.objects.filter(
            user=user, type=Notification.Type.SYSTEM
        ).latest("id")
        assert note.payload["reason"] == "TIMEOUT"
    audit = AuditLog.objects.get(action="CONNECTION_EXPIRED")
    assert audit.meta == {"reason": "TIMEOUT", "from_status": "PENDING"}


def test_accept_when_room_locked_returns_room_locked():
    owner, target = pair()
    open_window()
    room = make_room(owner)
    row = make_connection(
        initiator=owner,
        target=target,
        room=room,
        capacity_pref=None,
    )
    room.status = "LOCKED"
    room.save(update_fields=["status"])

    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")

    assert response.status_code == 409
    assert error_code(response) == "ROOM_LOCKED"


def test_decline_by_target():
    actor, target, row = _pending()

    response = auth_client(target).post(f"/api/connections/{row.pk}/decline")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "DECLINED"
    assert payload["close_reason"] == "DECLINED"
    row.refresh_from_db()
    assert row.close_reason == "DECLINED"
    note = Notification.objects.get(user=actor, type=Notification.Type.DECLINED)
    assert note.payload["connection_id"] == row.pk
    audit = AuditLog.objects.get(action="CONNECTION_DECLINED")
    assert audit.meta == {"reason": "DECLINED"}


def test_decline_requires_window():
    _, target, row = _pending()
    from apps.adminops.models import TimeWindow

    TimeWindow.objects.all().delete()
    response = auth_client(target).post(f"/api/connections/{row.pk}/decline")
    assert response.status_code == 409
    assert error_code(response) == "WINDOW_CLOSED"


def test_decline_by_initiator_forbidden():
    actor, _, row = _pending()
    response = auth_client(actor).post(f"/api/connections/{row.pk}/decline")
    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_cancel_pending_by_initiator():
    actor, target, row = _pending()

    response = auth_client(actor).post(f"/api/connections/{row.pk}/cancel")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "CANCELLED"
    assert payload["close_reason"] == "INITIATOR_CANCEL"
    note = Notification.objects.get(user=target, type=Notification.Type.SYSTEM)
    assert note.payload["reason"] == "INITIATOR_CANCEL"


def test_cancel_pending_by_target_forbidden():
    _, target, row = _pending()
    response = auth_client(target).post(f"/api/connections/{row.pk}/cancel")
    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_cancel_after_contact_shared_uses_end_understanding():
    actor, target, row = _pending()
    auth_client(target).post(f"/api/connections/{row.pk}/accept")

    response = auth_client(actor).post(f"/api/connections/{row.pk}/cancel")

    assert response.status_code == 200
    assert body(response)["close_reason"] == "END_UNDERSTANDING"
    row.refresh_from_db()
    assert row.status == "CANCELLED"


def test_cancel_does_not_require_window():
    from apps.adminops.models import TimeWindow

    actor, _, row = _pending()
    TimeWindow.objects.all().delete()
    response = auth_client(actor).post(f"/api/connections/{row.pk}/cancel")
    assert response.status_code == 200


def test_cancel_closed_request_returns_request_closed():
    actor, _, row = _pending()
    ConnectionRequest.objects.filter(pk=row.pk).update(
        status=ConnectionRequest.Status.CANCELLED,
        close_reason=ConnectionRequest.CloseReason.INITIATOR_CANCEL,
    )
    response = auth_client(actor).post(f"/api/connections/{row.pk}/cancel")
    assert response.status_code == 409
    assert error_code(response) == "REQUEST_CLOSED"


def test_contact_hidden_when_all_channels_off():
    actor, target, row = _pending()
    make_contact(actor, show_qq=False, show_wechat=False)
    auth_client(target).post(f"/api/connections/{row.pk}/accept")

    payload = body(auth_client(target).get(f"/api/connections/{row.pk}"))

    assert payload["status"] == "CONTACT_SHARED"
    assert payload["contact"] == {}
    assert payload["actions"]["can_view_contact"] is True


def test_contact_hidden_after_close():
    actor, target, row = _pending()
    make_contact(actor)
    auth_client(target).post(f"/api/connections/{row.pk}/accept")
    auth_client(target).post(f"/api/connections/{row.pk}/cancel")

    payload = body(auth_client(target).get(f"/api/connections/{row.pk}"))

    assert payload["contact"] == {}
    assert payload["close_reason"] == "END_UNDERSTANDING"
    assert payload["actions"]["can_cancel"] is False


def test_contact_hidden_when_open_but_expired():
    actor, target, row = _pending()
    make_contact(actor)
    auth_client(target).post(f"/api/connections/{row.pk}/accept")
    ConnectionRequest.objects.filter(pk=row.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    payload = body(auth_client(target).get(f"/api/connections/{row.pk}"))

    assert payload["status"] == "CONTACT_SHARED"
    assert payload["contact"] == {}
    assert payload["actions"]["can_view_contact"] is False


def test_actions_matrix_for_target_pending():
    _, target, row = _pending()
    payload = body(auth_client(target).get(f"/api/connections/{row.pk}"))
    assert payload["actions"] == {
        "can_accept": True,
        "can_decline": True,
        "can_cancel": False,
        "can_confirm": False,
        "can_pre_approve": False,
        "can_view_contact": False,
    }


def test_confirm_before_accept_returns_invalid_state():
    actor, _, row = _pending()
    response = auth_client(actor).post(f"/api/connections/{row.pk}/confirm")
    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"
