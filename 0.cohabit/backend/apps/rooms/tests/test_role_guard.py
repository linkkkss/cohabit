"""rooms 学生端写操作角色守卫（docs/02 §1.1 第 2 步、docs/06 S-06/S-14）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.rooms.models import Room, RoomMember, RoomTransfer

from .helpers import (
    PASSWORD,
    auth_client,
    body,
    make_room,
    make_user,
    open_window,
)

pytestmark = pytest.mark.django_db


def _admin() -> User:
    return User.objects.create_superuser(
        uid="2999999001",
        email="rooms-role-admin@example.com",
        password=PASSWORD,
        nickname="管理员",
        gender="MALE",
        grade=2,
        college="计算机学院",
        major="软件工程",
    )


def _owner_and_member() -> tuple[User, User]:
    owner = make_user(uid="1200000001", email="owner@example.com", nickname="小满")
    member = make_user(uid="1200000002", email="member@example.com", nickname="小林")
    return owner, member


def _pending_transfer(room: Room, owner: User, member: User) -> RoomTransfer:
    return RoomTransfer.objects.create(
        room=room,
        from_owner=owner,
        to_member=member,
        status=RoomTransfer.Status.PENDING,
        expires_at=timezone.now() + timedelta(hours=24),
    )


def test_admin_lock_is_forbidden():
    owner, _ = _owner_and_member()
    room = make_room(owner)
    open_window()

    response = auth_client(_admin()).post(f"/api/rooms/{room.pk}/lock")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert "学生" in response.json()["message"]
    room.refresh_from_db()
    assert room.status == Room.Status.RECRUITING


def test_admin_unknown_room_returns_403_not_404():
    response = auth_client(_admin()).post("/api/rooms/999999/lock")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_admin_patch_is_forbidden():
    owner, _ = _owner_and_member()
    room = make_room(owner, title="原来的寝室")

    response = auth_client(_admin()).patch(
        f"/api/rooms/{room.pk}",
        {"title": "管理员改名"},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    room.refresh_from_db()
    assert room.title == "原来的寝室"


def test_admin_transfer_accept_is_forbidden():
    owner, member = _owner_and_member()
    room = make_room(owner, members=(member,))
    open_window()
    transfer = _pending_transfer(room, owner, member)

    response = auth_client(_admin()).post(f"/api/room-transfers/{transfer.pk}/accept")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    transfer.refresh_from_db()
    assert transfer.status == RoomTransfer.Status.PENDING
    room.refresh_from_db()
    assert room.owner_id == owner.pk


def test_admin_unknown_transfer_returns_403_not_404():
    response = auth_client(_admin()).post("/api/room-transfers/999999/accept")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_student_transfer_accept_still_works():
    owner, member = _owner_and_member()
    room = make_room(owner, members=(member,))
    open_window()
    transfer = _pending_transfer(room, owner, member)

    response = auth_client(member).post(f"/api/room-transfers/{transfer.pk}/accept")

    assert response.status_code == 200
    assert body(response)["status"] == RoomTransfer.Status.ACCEPTED
    room.refresh_from_db()
    assert room.owner_id == member.pk
    assert RoomMember.objects.get(room=room, user=member).role == RoomMember.Role.OWNER


def test_admin_room_reads_and_public_page_still_work():
    owner, member = _owner_and_member()
    room = make_room(owner, members=(member,))
    admin_client = auth_client(_admin())

    square = admin_client.get("/api/rooms")
    assert square.status_code == 200

    detail = admin_client.get(f"/api/rooms/{room.code}")
    assert detail.status_code == 200
    assert body(detail)["id"] == room.pk

    public = APIClient().get(f"/api/public/rooms/{room.code}")
    assert public.status_code == 200
    assert body(public)["id"] == room.pk
