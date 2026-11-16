"""建寝每日限频（docs/04 §1.9）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.connections.tests.helpers import pair
from apps.rooms import services
from apps.rooms.exceptions import RoomRateLimited, TargetInRoom
from apps.rooms.models import Room, RoomMember

from .helpers import (
    auth_client,
    body,
    make_connection,
    make_room,
    make_user,
    open_window,
)

pytestmark = pytest.mark.django_db


def _seed_rooms(owner, count: int, *, created_at=None, start: int = 0) -> list[Room]:
    """直接落库的历史 Room；不建成员行，避免影响 ACTIVE 寝室守卫。"""
    rooms = [
        Room.objects.create(
            code=str(700_000_000 + start + index),
            title=f"{owner.nickname}的历史寝室",
            owner=owner,
            capacity=4,
            member_count=1,
            gender=owner.gender,
            college=owner.college,
            major=owner.major,
            tags=[],
            status=Room.Status.DISSOLVED,
            dissolved_at=timezone.now(),
        )
        for index in range(count)
    ]
    if created_at is not None:
        Room.objects.filter(pk__in=[room.pk for room in rooms]).update(
            created_at=created_at
        )
    return rooms


def _release(room: Room) -> None:
    """模拟寝室结束后释放 ACTIVE 成员，保留 Room 以参与当日计数。"""
    RoomMember.objects.filter(room=room).delete()


def test_first_five_creates_succeed_and_sixth_is_rejected():
    open_window()
    owner = make_user(uid="1300000001", email="rate-owner@example.com")
    peer = make_user(uid="1300000002", email="rate-peer@example.com")

    for _ in range(services.DAILY_ROOM_LIMIT):
        room = services.create_room_for_pair(owner, peer, 4)
        _release(room)

    assert Room.objects.filter(owner=owner).count() == services.DAILY_ROOM_LIMIT

    with pytest.raises(RoomRateLimited) as exc_info:
        services.create_room_for_pair(owner, peer, 4)

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after is not None
    assert exc_info.value.retry_after >= 1
    assert Room.objects.filter(owner=owner).count() == services.DAILY_ROOM_LIMIT


def test_sixth_confirm_returns_429_with_retry_after():
    initiator, target = pair()
    open_window()
    _seed_rooms(initiator, services.DAILY_ROOM_LIMIT)
    row = make_connection(initiator=initiator, target=target, capacity_pref=4)

    accepted = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert accepted.status_code == 200
    first = auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")
    assert first.status_code == 200
    assert body(first)["status"] == "CONFIRMING"

    limited = auth_client(target).post(f"/api/connections/{row.pk}/confirm")

    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"
    retry_after = int(limited["Retry-After"])
    assert retry_after >= 1
    assert retry_after <= 24 * 60 * 60
    assert Room.objects.filter(owner=initiator).count() == services.DAILY_ROOM_LIMIT


def test_rooms_created_yesterday_do_not_count_today():
    open_window()
    owner = make_user(uid="1300000011", email="rate-yesterday@example.com")
    peer = make_user(uid="1300000012", email="rate-yesterday-peer@example.com")
    _seed_rooms(
        owner,
        services.DAILY_ROOM_LIMIT,
        created_at=timezone.now() - timedelta(days=1, minutes=1),
        start=10,
    )

    room = services.create_room_for_pair(owner, peer, 4)

    assert room.owner_id == owner.pk
    assert Room.objects.filter(owner=owner).count() == services.DAILY_ROOM_LIMIT + 1


def test_target_and_other_users_have_independent_quota():
    open_window()
    owner = make_user(uid="1300000021", email="rate-a@example.com")
    peer = make_user(uid="1300000022", email="rate-b@example.com")
    other = make_user(uid="1300000023", email="rate-c@example.com")
    _seed_rooms(owner, services.DAILY_ROOM_LIMIT, start=20)

    room = services.create_room_for_pair(peer, other, 4)

    assert room.owner_id == peer.pk
    assert Room.objects.filter(owner=peer).count() == 1
    assert Room.objects.filter(owner=owner).count() == services.DAILY_ROOM_LIMIT


def test_failed_create_does_not_consume_daily_quota():
    open_window()
    owner = make_user(uid="1300000031", email="rate-fail@example.com")
    peer = make_user(uid="1300000032", email="rate-fail-peer@example.com")
    blocker = make_user(uid="1300000033", email="rate-fail-blocker@example.com")
    make_room(blocker, members=(peer,))

    with pytest.raises(TargetInRoom):
        services.create_room_for_pair(owner, peer, 4)

    assert Room.objects.filter(owner=owner).count() == 0
    RoomMember.objects.filter(room__owner=blocker).delete()

    for _ in range(services.DAILY_ROOM_LIMIT):
        room = services.create_room_for_pair(owner, peer, 4)
        _release(room)

    assert Room.objects.filter(owner=owner).count() == services.DAILY_ROOM_LIMIT
