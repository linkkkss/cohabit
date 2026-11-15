"""两步确认与组寝成立（docs/02 §3.5、§3.6）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.adminops.models import AuditLog, TimeWindow
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.rooms.models import Room, RoomMember

from .helpers import (
    auth_client,
    body,
    complete_profile,
    error_code,
    make_connection,
    make_room,
    make_user,
    open_window,
    pair,
)

pytestmark = pytest.mark.django_db


def _accepted(*, capacity_pref: int = 4) -> tuple:
    initiator, target = pair()
    open_window()
    row = make_connection(
        initiator=initiator,
        target=target,
        capacity_pref=capacity_pref,
    )
    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 200
    return initiator, target, row


def _room_invitation(*, capacity: int = 4) -> tuple:
    owner, target = pair()
    open_window()
    room = make_room(owner, capacity=capacity)
    row = make_connection(
        initiator=owner,
        target=target,
        room=room,
        capacity_pref=None,
    )
    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 200
    return owner, target, room, row


def _application(*, capacity: int = 4) -> tuple:
    owner, applicant = pair()
    open_window()
    room = make_room(owner, capacity=capacity)
    row = make_connection(
        initiator=applicant,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
        capacity_pref=None,
    )
    response = auth_client(owner).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 200
    return owner, applicant, room, row


def test_first_confirm_moves_to_confirming():
    initiator, target, row = _accepted()

    response = auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "CONFIRMING"
    assert payload["initiator_confirm_at"] is not None
    assert payload["target_confirm_at"] is None
    assert payload["room"] is None
    row.refresh_from_db()
    assert row.status == "CONFIRMING"
    assert row.initiator_confirm_at is not None
    assert abs(row.expires_at - (timezone.now() + timedelta(hours=48))) < timedelta(
        minutes=2
    )
    note = Notification.objects.get(
        user=target, type=Notification.Type.CONFIRM_PENDING
    )
    assert note.payload == {"connection_id": row.pk}
    audit = AuditLog.objects.get(action="CONNECTION_CONFIRMED_STEP1")
    assert audit.meta["to"] == "CONFIRMING"
    assert audit.meta["expires_at"].endswith("Z")
    assert Room.objects.count() == 0


def test_first_confirm_twice_returns_already_confirmed():
    initiator, _, row = _accepted()
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "ALREADY_CONFIRMED"


def test_second_confirm_creates_room_for_pair():
    initiator, target, row = _accepted(capacity_pref=4)
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "CONFIRMED"
    assert payload["close_reason"] == ""
    assert payload["room"]["code"]
    room = Room.objects.get(pk=payload["room"]["id"])
    assert room.owner_id == initiator.pk
    assert room.capacity == 4
    assert room.member_count == 2
    assert room.status == "RECRUITING"
    assert room.gender == initiator.gender
    assert room.college == initiator.college
    assert RoomMember.objects.get(room=room, user=initiator).role == "OWNER"
    member = RoomMember.objects.get(room=room, user=target)
    assert member.role == "MEMBER"
    assert member.status == "ACTIVE"
    for user in (initiator, target):
        note = Notification.objects.get(
            user=user, type=Notification.Type.CONFIRMED
        )
        assert note.payload["room_code"] == room.code
        assert note.payload["connection_id"] == row.pk
    audit = AuditLog.objects.get(action="CONNECTION_CONFIRMED")
    assert audit.meta["room_code"] == room.code
    assert audit.meta["type"] == "INVITE"


def _assert_room_persisted(row, payload, viewer):
    """成立后连接表的 room 外键必须落库，详情接口可回读。"""
    row.refresh_from_db()
    assert row.status == ConnectionRequest.Status.CONFIRMED
    assert row.room_id == payload["room"]["id"]

    detail = auth_client(viewer).get(f"/api/connections/{row.pk}")
    assert detail.status_code == 200
    detail_payload = body(detail)
    assert detail_payload["room"] is not None
    assert detail_payload["room"]["id"] == row.room_id
    assert detail_payload["room"]["code"] == payload["room"]["code"]


def test_second_confirm_persists_room_for_pair_connection():
    initiator, target, row = _accepted(capacity_pref=4)
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["room"] is not None
    _assert_room_persisted(row, payload, initiator)


def test_room_invitation_confirm_keeps_room_on_connection():
    owner, target, room, row = _room_invitation()
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["room"]["id"] == room.pk
    _assert_room_persisted(row, payload, owner)


def test_application_confirm_keeps_room_on_connection():
    owner, applicant, room, row = _application()
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(applicant).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["room"]["id"] == room.pk
    _assert_room_persisted(row, payload, owner)


def test_capacity_two_room_is_full_after_confirm():
    initiator, target, row = _accepted(capacity_pref=2)
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    room = Room.objects.get(pk=body(response)["room"]["id"])
    assert room.capacity == 2
    assert room.member_count == 2
    assert room.status == "FULL"
    for user in (initiator, target):
        note = Notification.objects.get(user=user, type=Notification.Type.ROOM_FULL)
        assert note.payload == {"room_code": room.code, "capacity": 2}


def test_confirm_closes_other_open_requests():
    initiator, target, row = _accepted()
    other = make_user()
    complete_profile(other)
    stale = make_connection(initiator=initiator, target=other)
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    stale.refresh_from_db()
    assert stale.status == "CANCELLED"
    assert stale.close_reason == "AUTO_CANCELLED"
    note = Notification.objects.get(user=other, type=Notification.Type.SYSTEM)
    assert note.payload["reason"] == "AUTO_CANCELLED"
    audit = AuditLog.objects.get(action="CONNECTION_AUTO_CANCELLED")
    assert audit.target_id == stale.pk
    assert audit.meta["reason"] == "AUTO_CANCELLED"


def test_room_invitation_join_adds_member():
    owner, target, room, row = _room_invitation()
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    assert body(response)["status"] == "CONFIRMED"
    room.refresh_from_db()
    assert room.member_count == 2
    assert room.status == "RECRUITING"
    assert RoomMember.objects.get(room=room, user=target).status == "ACTIVE"
    note = Notification.objects.get(
        user=owner, type=Notification.Type.MEMBER_JOINED
    )
    assert note.payload["room_code"] == room.code
    assert note.payload["member_count"] == 2
    for user in (owner, target):
        note = Notification.objects.get(
            user=user, type=Notification.Type.CONFIRMED
        )
        assert note.payload["room_code"] == room.code


def test_application_join_adds_applicant():
    owner, applicant, room, row = _application()
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(applicant).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    room.refresh_from_db()
    assert room.member_count == 2
    assert RoomMember.objects.get(room=room, user=applicant).status == "ACTIVE"


def test_join_when_room_became_full_returns_room_full():
    owner, target, room, row = _room_invitation(capacity=2)
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")
    filler = make_user()
    complete_profile(filler)
    RoomMember.objects.create(
        room=room,
        user=filler,
        role=RoomMember.Role.MEMBER,
        status=RoomMember.Status.ACTIVE,
    )
    Room.objects.filter(pk=room.pk).update(member_count=2, status="FULL")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "ROOM_FULL"
    row.refresh_from_db()
    assert row.status == "CONFIRMING"


def test_confirm_when_room_locked_returns_room_locked():
    owner, target, room, row = _room_invitation()
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")
    Room.objects.filter(pk=room.pk).update(status="LOCKED")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "ROOM_LOCKED"


def test_confirm_requires_open_window():
    initiator, target, row = _accepted()
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")
    TimeWindow.objects.all().delete()

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "WINDOW_CLOSED"


def test_confirm_expired_returns_request_expired():
    initiator, target, row = _accepted()
    ConnectionRequest.objects.filter(pk=row.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    response = auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "REQUEST_EXPIRED"
    row.refresh_from_db()
    assert row.status == "EXPIRED"
    assert row.close_reason == "TIMEOUT"
    assert Room.objects.count() == 0


def test_confirm_when_target_already_in_room_returns_target_in_room():
    initiator, target, row = _accepted()
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")
    make_room(target)

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 409
    assert error_code(response) == "TARGET_IN_ROOM"


def test_expire_due_connections_is_idempotent():
    first = _accepted()
    second = _accepted()
    past = timezone.now() - timedelta(minutes=5)
    ConnectionRequest.objects.filter(pk__in=[first[2].pk, second[2].pk]).update(
        expires_at=past
    )

    from apps.connections.services import expire_due_connections

    assert expire_due_connections() == 2
    assert expire_due_connections() == 0
    for _, _, row in (first, second):
        row.refresh_from_db()
        assert row.status == "EXPIRED"
        assert row.close_reason == "TIMEOUT"
    assert AuditLog.objects.filter(action="CONNECTION_EXPIRED").count() == 2


def test_confirm_updates_version():
    initiator, target, row = _accepted()
    row.refresh_from_db()
    assert row.version == 1
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")
    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")
    assert body(response)["version"] == 3


def _confirm_both(left, right, row) -> dict:
    first = auth_client(left).post(f"/api/connections/{row.pk}/confirm")
    assert first.status_code == 200
    second = auth_client(right).post(f"/api/connections/{row.pk}/confirm")
    assert second.status_code == 200
    return body(second)


def test_confirmed_request_clears_expires_at_for_pair_connection():
    initiator, target, row = _accepted(capacity_pref=4)

    payload = _confirm_both(initiator, target, row)

    assert payload["status"] == "CONFIRMED"
    assert payload["expires_at"] is None
    row.refresh_from_db()
    assert row.expires_at is None


def test_confirmed_request_clears_expires_at_for_room_invitation():
    owner, target, _room, row = _room_invitation()

    payload = _confirm_both(owner, target, row)

    assert payload["status"] == "CONFIRMED"
    assert payload["expires_at"] is None
    row.refresh_from_db()
    assert row.expires_at is None


def test_confirmed_request_clears_expires_at_for_application():
    owner, applicant, _room, row = _application()

    payload = _confirm_both(owner, applicant, row)

    assert payload["status"] == "CONFIRMED"
    assert payload["expires_at"] is None
    row.refresh_from_db()
    assert row.expires_at is None


def test_open_states_keep_expires_at():
    _initiator, _target, pending = _accepted()

    other_initiator, other_target, confirming = _accepted()
    auth_client(other_initiator).post(f"/api/connections/{confirming.pk}/confirm")

    for row, status in (
        (pending, ConnectionRequest.Status.CONTACT_SHARED),
        (confirming, ConnectionRequest.Status.CONFIRMING),
    ):
        row.refresh_from_db()
        assert row.status == status
        assert row.expires_at is not None


def test_pending_request_has_expires_at_set():
    initiator, target = pair()
    open_window()
    row = make_connection(initiator=initiator, target=target, capacity_pref=4)

    row.refresh_from_db()
    assert row.status == ConnectionRequest.Status.PENDING
    assert row.expires_at is not None
    assert row.expires_at > timezone.now()


def test_expires_at_allows_null():
    initiator, target = pair()
    open_window()
    row = make_connection(initiator=initiator, target=target, capacity_pref=4)

    ConnectionRequest.objects.filter(pk=row.pk).update(expires_at=None)

    row.refresh_from_db()
    assert row.expires_at is None
    # 过期时间为空时懒过期逻辑必须安全跳过（不得抛 TypeError）。
    from apps.connections.services import expire_due_connections

    assert expire_due_connections() == 0
    row.refresh_from_db()
    assert row.status == ConnectionRequest.Status.PENDING


def _assert_room_snapshot(payload, viewer, *, member_count, status) -> None:
    """confirm 响应里的 room 快照必须与 DB / GET 一致（不得滞后）。"""
    snapshot = payload["room"]
    assert snapshot["member_count"] == member_count
    assert snapshot["status"] == status

    room = Room.objects.get(pk=snapshot["id"])
    assert room.member_count == member_count
    assert room.status == status

    detail = auth_client(viewer).get(f"/api/rooms/{room.pk}")
    assert detail.status_code == 200
    detail_payload = body(detail)
    assert detail_payload["member_count"] == member_count
    assert detail_payload["status"] == status


def _room_invitation_with_member(*, capacity: int = 6) -> tuple:
    """房主 + 1 名既有成员，邀请第三人；成立后 member_count 2 → 3。"""
    owner, target = pair()
    extra = make_user()
    complete_profile(extra)
    open_window()
    room = make_room(owner, capacity=capacity, members=(extra,))
    row = make_connection(
        initiator=owner,
        target=target,
        room=room,
        capacity_pref=None,
    )
    response = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 200
    return owner, target, room, row


def _application_with_member(*, capacity: int = 6) -> tuple:
    """房主 + 1 名既有成员，受理第三人申请；成立后 member_count 2 → 3。"""
    owner, applicant = pair()
    extra = make_user()
    complete_profile(extra)
    open_window()
    room = make_room(owner, capacity=capacity, members=(extra,))
    row = make_connection(
        initiator=applicant,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
        capacity_pref=None,
    )
    response = auth_client(owner).post(f"/api/connections/{row.pk}/accept")
    assert response.status_code == 200
    return owner, applicant, room, row


def test_room_invitation_confirm_response_reports_updated_room():
    owner, target, room, row = _room_invitation_with_member()
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "CONFIRMED"
    assert payload["room"]["id"] == room.pk
    _assert_room_snapshot(payload, target, member_count=3, status="RECRUITING")


def test_application_confirm_response_reports_updated_room():
    owner, applicant, room, row = _application_with_member()
    auth_client(owner).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(applicant).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == "CONFIRMED"
    assert payload["room"]["id"] == room.pk
    _assert_room_snapshot(payload, applicant, member_count=3, status="RECRUITING")


def test_pair_confirm_response_reports_created_room():
    initiator, target, row = _accepted(capacity_pref=6)
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["room"]["capacity"] == 6
    _assert_room_snapshot(payload, target, member_count=2, status="RECRUITING")


def test_capacity_two_confirm_response_reports_full_room():
    initiator, target, row = _accepted(capacity_pref=2)
    auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")

    response = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 200
    payload = body(response)
    assert payload["room"]["capacity"] == 2
    _assert_room_snapshot(payload, target, member_count=2, status="FULL")

