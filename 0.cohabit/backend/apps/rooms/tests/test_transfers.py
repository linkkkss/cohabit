"""房主转让 API / 服务测试（docs/04 §4.3、docs/02 §6）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.adminops.models import AuditLog, TimeWindow
from apps.notifications.models import Notification
from apps.rooms.models import Room, RoomMember, RoomTransfer
from apps.rooms.tests.helpers import (
    auth_client,
    body,
    error_code,
    make_room,
    make_user,
    open_window,
)
from apps.rooms.transfer_services import expire_due_transfers

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def window():
    return open_window()


@pytest.fixture
def owner():
    return make_user(uid="1000000001", email="owner@example.com", nickname="小满")


@pytest.fixture
def member():
    return make_user(uid="1000000002", email="member@example.com", nickname="小林")


@pytest.fixture
def outsider():
    return make_user(uid="1000000003", email="outsider@example.com", nickname="阿泽")


@pytest.fixture
def room(owner, member):
    return make_room(owner, members=(member,))


def _make_transfer(room, owner, member, *, expires_in=timedelta(hours=24), status=None):
    return RoomTransfer.objects.create(
        room=room,
        from_owner=owner,
        to_member=member,
        status=status or RoomTransfer.Status.PENDING,
        expires_at=timezone.now() + expires_in,
    )


# --------------------------------------------------------------------------- #
# 创建
# --------------------------------------------------------------------------- #
def test_create_transfer_returns_pending(room, owner, member):
    response = auth_client(owner).post(
        f"/api/rooms/{room.pk}/transfer", {"to_uid": member.uid}, format="json"
    )

    assert response.status_code == 201
    payload = body(response)
    assert payload["status"] == RoomTransfer.Status.PENDING
    assert payload["from_owner"]["uid"] == owner.uid
    assert payload["to_member"]["uid"] == member.uid
    assert AuditLog.objects.filter(action="TRANSFER_CREATED").exists()
    notification = Notification.objects.get(type=Notification.Type.TRANSFER_RECEIVED)
    assert notification.user_id == member.pk
    assert notification.payload["from_nickname"] == owner.nickname


def test_create_transfer_expires_in_24_hours(room, owner, member):
    before = timezone.now()

    response = auth_client(owner).post(
        f"/api/rooms/{room.pk}/transfer", {"to_uid": member.uid}, format="json"
    )

    assert response.status_code == 201
    created = RoomTransfer.objects.get(pk=body(response)["id"], room=room)
    delta = created.expires_at - before
    assert timedelta(hours=23, minutes=59) < delta < timedelta(hours=24, minutes=1)


def test_create_transfer_duplicate_returns_conflict(room, owner, member):
    _make_transfer(room, owner, member)

    response = auth_client(owner).post(
        f"/api/rooms/{room.pk}/transfer", {"to_uid": member.uid}, format="json"
    )

    assert response.status_code == 409
    assert error_code(response) == "TRANSFER_EXISTS"


def test_create_transfer_requires_owner(room, member, owner):
    response = auth_client(member).post(
        f"/api/rooms/{room.pk}/transfer", {"to_uid": owner.uid}, format="json"
    )

    assert response.status_code == 403
    assert error_code(response) == "NOT_OWNER"


def test_create_transfer_rejects_non_member(room, owner, outsider):
    response = auth_client(owner).post(
        f"/api/rooms/{room.pk}/transfer", {"to_uid": outsider.uid}, format="json"
    )

    assert response.status_code == 400
    assert error_code(response) == "INVALID_TARGET"


def test_create_transfer_rejects_self(room, owner):
    response = auth_client(owner).post(
        f"/api/rooms/{room.pk}/transfer", {"to_uid": owner.uid}, format="json"
    )

    assert response.status_code == 400
    assert error_code(response) == "INVALID_TARGET"


def test_create_transfer_requires_window(room, owner, member):
    TimeWindow.objects.filter(college=room.college).update(
        start_at=timezone.now() - timedelta(hours=4),
        end_at=timezone.now() - timedelta(hours=3),
    )

    response = auth_client(owner).post(
        f"/api/rooms/{room.pk}/transfer", {"to_uid": member.uid}, format="json"
    )

    assert response.status_code == 409
    assert error_code(response) == "WINDOW_CLOSED"


def test_create_transfer_requires_to_uid(room, owner):
    response = auth_client(owner).post(f"/api/rooms/{room.pk}/transfer", {}, format="json")

    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"


# --------------------------------------------------------------------------- #
# 接受
# --------------------------------------------------------------------------- #
def test_accept_transfer_swaps_owner_and_roles(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/accept")

    assert response.status_code == 200
    assert body(response)["status"] == RoomTransfer.Status.ACCEPTED
    transfer.refresh_from_db()
    room.refresh_from_db()
    assert transfer.decided_at is not None
    assert room.owner_id == member.pk
    assert RoomMember.objects.get(room=room, user=member).role == RoomMember.Role.OWNER
    assert RoomMember.objects.get(room=room, user=owner).role == RoomMember.Role.MEMBER
    assert room.member_count == 2
    notifications = Notification.objects.filter(
        type=Notification.Type.TRANSFER_ACCEPTED
    )
    assert set(notifications.values_list("user_id", flat=True)) == {
        owner.pk,
        member.pk,
    }
    audit = AuditLog.objects.get(action="TRANSFER_ACCEPTED")
    assert audit.meta == {
        "room_id": room.pk,
        "from_owner_id": owner.pk,
        "to_member_id": member.pk,
    }


def test_accept_transfer_requires_target(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    response = auth_client(owner).post(f"/api/room-transfers/{transfer.pk}/accept")

    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_accept_expired_transfer_returns_409(room, owner, member):
    transfer = _make_transfer(room, owner, member, expires_in=timedelta(minutes=-1))

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/accept")

    assert response.status_code == 409
    assert error_code(response) == "TRANSFER_EXPIRED"


def test_accept_twice_returns_invalid_state(room, owner, member):
    transfer = _make_transfer(room, owner, member)
    auth_client(member).post(f"/api/room-transfers/{transfer.pk}/accept")

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/accept")

    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"


def test_accept_requires_window(room, owner, member):
    transfer = _make_transfer(room, owner, member)
    TimeWindow.objects.filter(college=room.college).update(
        start_at=timezone.now() - timedelta(hours=4),
        end_at=timezone.now() - timedelta(hours=3),
    )

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/accept")

    assert response.status_code == 409
    assert error_code(response) == "WINDOW_CLOSED"


def test_accept_unknown_transfer_returns_404():
    viewer = make_user(uid="1000000007", email="v@example.com", nickname="小周")

    response = auth_client(viewer).post("/api/room-transfers/999999/accept")

    assert response.status_code == 404
    assert error_code(response) == "TRANSFER_NOT_FOUND"


# --------------------------------------------------------------------------- #
# 拒绝 / 撤回
# --------------------------------------------------------------------------- #
def test_decline_transfer_notifies_owner(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/decline")

    assert response.status_code == 200
    assert body(response)["status"] == RoomTransfer.Status.DECLINED
    notification = Notification.objects.get(type=Notification.Type.TRANSFER_DECLINED)
    assert notification.user_id == owner.pk
    assert AuditLog.objects.filter(action="TRANSFER_DECLINED").exists()


def test_decline_requires_target(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    response = auth_client(owner).post(f"/api/room-transfers/{transfer.pk}/decline")

    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_decline_does_not_need_window(room, owner, member):
    transfer = _make_transfer(room, owner, member)
    TimeWindow.objects.all().delete()

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/decline")

    assert response.status_code == 200


def test_cancel_transfer_notifies_target(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    response = auth_client(owner).post(f"/api/room-transfers/{transfer.pk}/cancel")

    assert response.status_code == 200
    assert body(response)["status"] == RoomTransfer.Status.CANCELLED
    notification = Notification.objects.get(type=Notification.Type.TRANSFER_CANCELLED)
    assert notification.user_id == member.pk
    assert notification.payload["reason"] == "INITIATOR_CANCEL"


def test_cancel_requires_original_owner(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/cancel")

    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


# --------------------------------------------------------------------------- #
# 自动取消 / 过期
# --------------------------------------------------------------------------- #
def test_member_leave_cancels_pending_transfer(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    auth_client(member).post(f"/api/rooms/{room.pk}/leave")

    transfer.refresh_from_db()
    assert transfer.status == RoomTransfer.Status.CANCELLED
    cancelled = Notification.objects.filter(type=Notification.Type.TRANSFER_CANCELLED)
    assert set(cancelled.values_list("user_id", flat=True)) == {owner.pk, member.pk}


def test_remove_member_cancels_pending_transfer(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    auth_client(owner).delete(f"/api/rooms/{room.pk}/members/{member.uid}")

    transfer.refresh_from_db()
    assert transfer.status == RoomTransfer.Status.CANCELLED


def test_dissolve_cancels_pending_transfer(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    auth_client(owner).post(f"/api/rooms/{room.pk}/dissolve")

    transfer.refresh_from_db()
    assert transfer.status == RoomTransfer.Status.CANCELLED


def test_expire_due_transfers_marks_expired(room, owner, member):
    transfer = _make_transfer(room, owner, member, expires_in=timedelta(minutes=-5))

    expired = expire_due_transfers()

    transfer.refresh_from_db()
    assert expired == 1
    assert transfer.status == RoomTransfer.Status.EXPIRED
    notifications = Notification.objects.filter(type=Notification.Type.TRANSFER_EXPIRED)
    assert set(notifications.values_list("user_id", flat=True)) == {owner.pk, member.pk}
    assert AuditLog.objects.filter(action="TRANSFER_EXPIRED").exists()


def test_expire_due_transfers_skips_future(room, owner, member):
    transfer = _make_transfer(room, owner, member, expires_in=timedelta(hours=1))

    assert expire_due_transfers() == 0
    transfer.refresh_from_db()
    assert transfer.status == RoomTransfer.Status.PENDING


def test_room_detail_shows_transfer_to_outsider_without_contact(room, owner, member, outsider):
    _make_transfer(room, owner, member)

    response = auth_client(outsider).get(f"/api/rooms/{room.pk}")

    assert response.status_code == 200
    assert "contact" not in str(body(response))


def test_room_detail_shows_transfer_to_member(room, owner, member):
    transfer = _make_transfer(room, owner, member)

    payload = body(auth_client(member).get(f"/api/rooms/{room.pk}"))

    assert payload["pending_transfer"]["id"] == transfer.pk
    assert payload["pending_transfer"]["to_member"]["uid"] == member.uid
    assert Room.objects.count() == 1

