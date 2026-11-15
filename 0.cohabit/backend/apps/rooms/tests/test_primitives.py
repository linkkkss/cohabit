"""寝室 service 原语测试（docs/02 §3.5.4、§4、§11）。

覆盖 connections 状态机将要复用的四个原语：
``generate_room_code`` / ``create_room_for_pair`` / ``join_room_for_confirm`` /
``close_open_requests_for_room``，以及容量、窗、锁与副作用的幂等边界。
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.adminops.models import AuditLog, TimeWindow
from apps.connections.models import ConnectionRequest
from apps.core.timewindow import WindowClosed
from apps.notifications.models import Notification
from apps.profiles.models import Profile
from apps.rooms import services
from apps.rooms.exceptions import (
    AlreadyInRoom,
    CapacityInvalid,
    RoomArchived,
    RoomCodeGenerationFailed,
    RoomDissolved,
    RoomFull,
    RoomLocked,
    TargetInRoom,
)
from apps.rooms.models import Room, RoomMember

from .helpers import make_connection, make_room, make_user, open_window

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def window():
    return open_window()


@pytest.fixture
def owner():
    return make_user(uid="1000000001", email="owner@example.com", nickname="小满")


@pytest.fixture
def peer():
    return make_user(uid="1000000002", email="peer@example.com", nickname="小林")


@pytest.fixture
def third():
    return make_user(uid="1000000003", email="third@example.com", nickname="阿泽")


# --------------------------------------------------------------------------
# generate_room_code
# --------------------------------------------------------------------------


def test_generate_room_code_is_nine_digits():
    code = services.generate_room_code()

    assert len(code) == 9
    assert code.isdigit()
    assert code[0] != "0"


def test_generate_room_code_is_unique_across_calls():
    codes = {services.generate_room_code() for _ in range(50)}

    assert len(codes) == 50


def test_generate_room_code_retries_on_collision(monkeypatch, owner):
    make_room(owner, code="123456789")
    sequence = iter([23_456_789, 23_456_789, 87_654_321])
    monkeypatch.setattr(services.secrets, "randbelow", lambda _n: next(sequence))

    assert services.generate_room_code() == "187654321"


def test_generate_room_code_exhausts_attempts(monkeypatch, owner):
    make_room(owner, code="123456789")
    monkeypatch.setattr(services.secrets, "randbelow", lambda _n: 23_456_789)

    with pytest.raises(RoomCodeGenerationFailed):
        services.generate_room_code()


# --------------------------------------------------------------------------
# create_room_for_pair
# --------------------------------------------------------------------------


def test_create_room_for_pair_builds_recruiting_room(owner, peer):
    room = services.create_room_for_pair(owner, peer, 4)

    assert room.code.isdigit() and len(room.code) == 9
    assert room.status == Room.Status.RECRUITING
    assert room.capacity == 4
    assert room.member_count == 2
    assert room.owner_id == owner.pk
    assert room.title == "小满的寝室"
    assert room.gender == owner.gender
    assert room.college == owner.college
    assert room.tags == []
    assert list(
        room.members.order_by("user_id").values_list("user_id", "role", "status")
    ) == [
        (owner.pk, RoomMember.Role.OWNER, RoomMember.Status.ACTIVE),
        (peer.pk, RoomMember.Role.MEMBER, RoomMember.Status.ACTIVE),
    ]


def test_create_room_for_pair_capacity_two_is_full(owner, peer):
    room = services.create_room_for_pair(owner, peer, 2)

    assert room.status == Room.Status.FULL
    assert room.member_count == 2
    assert room.capacity == 2


def test_create_room_for_pair_notifies_both_sides(owner, peer):
    room = services.create_room_for_pair(owner, peer, 4)

    confirmed = Notification.objects.filter(type=Notification.Type.CONFIRMED)
    assert set(confirmed.values_list("user_id", flat=True)) == {owner.pk, peer.pk}
    for notification in confirmed:
        assert notification.payload["room_code"] == room.code
        assert notification.payload["room_title"] == room.title


def test_create_room_for_pair_capacity_two_also_sends_room_full(owner, peer):
    room = services.create_room_for_pair(owner, peer, 2)

    full = Notification.objects.filter(type=Notification.Type.ROOM_FULL)
    assert set(full.values_list("user_id", flat=True)) == {owner.pk, peer.pk}
    assert full.first().payload == {"room_code": room.code, "capacity": 2}


def test_create_room_for_pair_writes_room_created_audit(owner, peer):
    room = services.create_room_for_pair(owner, peer, 4, request_id="req-1")

    audit = AuditLog.objects.get(action="ROOM_CREATED", target_type="ROOM")
    assert audit.target_id == room.pk
    assert audit.actor_id == owner.pk
    assert audit.request_id == "req-1"
    assert audit.meta == {
        "capacity": 4,
        "gender": owner.gender,
        "college": owner.college,
    }


def test_create_room_for_pair_records_connection_id(owner, peer):
    request = make_connection(initiator=owner, target=peer, capacity_pref=4)

    services.create_room_for_pair(owner, peer, 4, connection=request)

    audit = AuditLog.objects.get(action="ROOM_CREATED")
    assert audit.meta["connection_id"] == request.pk
    assert AuditLog.objects.filter(
        action="CONNECTION_CLOSED_FULL", target_type="CONNECTION"
    ).count() == 0


def test_create_room_for_pair_merges_profile_tags(owner, peer):
    Profile.objects.update_or_create(user=owner, defaults={"tags": ["早睡", "安静"]})
    Profile.objects.update_or_create(user=peer, defaults={"tags": ["安静", "爱干净"]})

    room = services.create_room_for_pair(owner, peer, 4)

    assert room.tags == ["早睡", "安静", "爱干净"]


def test_default_room_title_is_truncated_to_thirty_chars():
    long_nickname = SimpleNamespace(nickname="长" * 40)

    assert len(services.default_room_title(long_nickname)) == 30


def test_create_room_for_pair_rejects_invalid_capacity(owner, peer):
    with pytest.raises(CapacityInvalid):
        services.create_room_for_pair(owner, peer, 3)


def test_create_room_for_pair_requires_open_window(owner, peer):
    TimeWindow.objects.all().delete()

    with pytest.raises(WindowClosed):
        services.create_room_for_pair(owner, peer, 4)


def test_create_room_for_pair_requires_same_gender(window, owner):
    other = make_user(
        uid="1000000009", email="girl@example.com", nickname="小禾", gender="FEMALE"
    )

    with pytest.raises(Exception) as excinfo:
        services.create_room_for_pair(owner, other, 4)

    assert getattr(excinfo.value, "error_code", "") == "FORBIDDEN"


def test_create_room_for_pair_rejects_initiator_already_in_room(owner, peer):
    make_room(owner, members=(peer,))

    with pytest.raises(AlreadyInRoom):
        services.create_room_for_pair(owner, peer, 4)


def test_create_room_for_pair_rejects_target_already_in_room(owner, peer, third):
    make_room(peer, members=(third,))

    with pytest.raises(TargetInRoom):
        services.create_room_for_pair(owner, peer, 4)


# --------------------------------------------------------------------------
# join_room_for_confirm
# --------------------------------------------------------------------------


def test_join_room_for_confirm_adds_member(owner, peer, third):
    room = make_room(owner, members=(peer,))

    member = services.join_room_for_confirm(room, third)

    room.refresh_from_db()
    assert member.status == RoomMember.Status.ACTIVE
    assert member.role == RoomMember.Role.MEMBER
    assert room.member_count == 3
    assert room.status == Room.Status.RECRUITING


def test_join_room_for_confirm_notifies_existing_members(owner, peer, third):
    room = make_room(owner, members=(peer,))

    services.join_room_for_confirm(room, third)

    joined = Notification.objects.filter(type=Notification.Type.MEMBER_JOINED)
    assert set(joined.values_list("user_id", flat=True)) == {owner.pk, peer.pk}
    assert joined.first().payload == {
        "room_code": room.code,
        "nickname": third.nickname,
        "member_count": 3,
        "capacity": 4,
    }
    assert not Notification.objects.filter(
        user=third, type=Notification.Type.MEMBER_JOINED
    ).exists()


def test_join_room_for_confirm_writes_audit(owner, peer, third):
    room = make_room(owner, capacity=6, members=(peer,))

    member = services.join_room_for_confirm(room, third)

    audit = AuditLog.objects.get(action="MEMBER_JOINED")
    assert audit.target_type == "ROOM"
    assert audit.target_id == member.pk
    assert audit.meta["room_id"] == room.pk
    assert audit.meta["user_id"] == third.pk
    assert audit.meta["role"] == "MEMBER"
    assert audit.actor_id == third.pk
    assert member.pk


def test_join_room_for_confirm_fills_room_and_sets_full(owner, peer, third):
    filler = make_user(uid="1000000011", email="filler@example.com", nickname="小填")
    room = make_room(owner, members=(peer, filler))
    request = make_connection(
        initiator=third,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    services.join_room_for_confirm(room, third, request)

    room.refresh_from_db()
    request.refresh_from_db()
    assert room.status == Room.Status.FULL
    assert room.member_count == 4
    assert request.status == ConnectionRequest.Status.CANCELLED
    assert request.close_reason == ConnectionRequest.CloseReason.FULL
    assert AuditLog.objects.filter(action="ROOM_FULL").exists()
    assert AuditLog.objects.filter(action="CONNECTION_CLOSED_FULL").exists()
    assert Notification.objects.filter(type=Notification.Type.ROOM_FULL).count() == 4
    system = Notification.objects.filter(type=Notification.Type.SYSTEM)
    assert set(system.values_list("user_id", flat=True)) == {third.pk, owner.pk}
    assert system.first().payload["reason"] == "FULL"


def test_join_room_for_confirm_rejects_locked_room(owner, peer):
    room = make_room(owner, status=Room.Status.LOCKED)

    with pytest.raises(RoomLocked):
        services.join_room_for_confirm(room, peer)


def test_join_room_for_confirm_rejects_full_room(owner, peer, third):
    room = make_room(owner, capacity=2, members=(peer,), status=Room.Status.FULL)

    with pytest.raises(RoomFull):
        services.join_room_for_confirm(room, third)


def test_join_room_for_confirm_rejects_archived_room(owner, peer):
    room = make_room(owner, status=Room.Status.ARCHIVED)

    with pytest.raises(RoomArchived):
        services.join_room_for_confirm(room, peer)


def test_join_room_for_confirm_rejects_dissolved_room(owner, peer):
    room = make_room(
        owner,
        status=Room.Status.DISSOLVED,
        member_count=0,
    )

    with pytest.raises(RoomDissolved):
        services.join_room_for_confirm(room, peer)


def test_join_room_for_confirm_rejects_existing_member(owner, peer):
    room = make_room(owner, members=(peer,))

    with pytest.raises(AlreadyInRoom):
        services.join_room_for_confirm(room, peer)


def test_join_room_for_confirm_requires_open_window(owner, peer):
    room = make_room(owner)
    room.college = "外国语学院"
    room.save(update_fields=["college"])
    open_window("计算机学院")

    with pytest.raises(WindowClosed):
        services.join_room_for_confirm(room, peer)


# --------------------------------------------------------------------------
# close_open_requests_for_room
# --------------------------------------------------------------------------


def test_close_open_requests_closes_room_scoped_requests(owner, peer, third):
    room = make_room(owner, members=(peer,), capacity=6)
    invite = make_connection(
        initiator=owner,
        target=third,
        type=ConnectionRequest.Type.INVITE,
        room=room,
    )
    apply_request = make_connection(
        initiator=third,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    closed = services.close_open_requests_for_room(
        room, ConnectionRequest.CloseReason.LOCKED, actor=owner
    )

    assert closed == 2
    invite.refresh_from_db()
    apply_request.refresh_from_db()
    assert invite.status == ConnectionRequest.Status.CANCELLED
    assert apply_request.status == ConnectionRequest.Status.CANCELLED
    assert invite.close_reason == "LOCKED"
    assert apply_request.close_reason == "LOCKED"
    assert invite.closed_by_id == owner.pk
    assert AuditLog.objects.filter(action="CONNECTION_CLOSED_LOCKED").count() == 2
    system = Notification.objects.filter(type=Notification.Type.SYSTEM)
    assert system.count() == 4
    assert {row.payload["reason"] for row in system} == {"LOCKED"}


def test_close_open_requests_skips_person_to_person_invites(owner, peer):
    room = make_room(owner, members=(peer,), capacity=6)
    pair_request = make_connection(initiator=owner, target=peer, capacity_pref=4)

    closed = services.close_open_requests_for_room(
        room, ConnectionRequest.CloseReason.FULL
    )

    assert closed == 0
    pair_request.refresh_from_db()
    assert pair_request.status == ConnectionRequest.Status.PENDING


def test_close_open_requests_honours_except_request(owner, peer, third):
    room = make_room(owner, members=(peer,), capacity=6)
    keep = make_connection(
        initiator=third,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    closed = services.close_open_requests_for_room(
        room,
        ConnectionRequest.CloseReason.FULL,
        except_request=keep,
    )

    assert closed == 0
    keep.refresh_from_db()
    assert keep.status == ConnectionRequest.Status.PENDING


def test_close_open_requests_only_touches_open_statuses(owner, peer, third):
    room = make_room(owner, members=(peer,), capacity=6)
    make_connection(
        initiator=third,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
        status=ConnectionRequest.Status.CONFIRMING,
    )

    closed = services.close_open_requests_for_room(
        room, ConnectionRequest.CloseReason.ARCHIVED
    )

    assert closed == 1


def test_close_open_requests_maps_reason_to_audit_action(owner, peer, third):
    room = make_room(owner, members=(peer,), capacity=6)
    make_connection(
        initiator=third,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    services.close_open_requests_for_room(
        room, ConnectionRequest.CloseReason.ROOM_DISSOLVED
    )

    audit = AuditLog.objects.get(action="CONNECTION_CLOSED_DISSOLVED")
    assert audit.target_type == "CONNECTION"
    assert audit.meta["reason"] == "ROOM_DISSOLVED"
    assert audit.meta["room_code"] == room.code


# --------------------------------------------------------------------------
# 状态机辅助
# --------------------------------------------------------------------------


def test_active_membership_ignores_left_rows(owner, peer):
    room = make_room(owner)
    RoomMember.objects.create(
        room=room, user=peer, role=RoomMember.Role.MEMBER, status=RoomMember.Status.LEFT
    )

    assert services.active_membership(owner).room_id == room.pk
    assert services.active_membership(peer) is None


def test_normalize_capacity_defaults_and_validates():
    assert services.normalize_capacity(None) == 4
    assert services.normalize_capacity("2") == 2
    with pytest.raises(CapacityInvalid):
        services.normalize_capacity(5)


def test_repair_member_count_fixes_drift(owner, peer):
    room = make_room(owner, members=(peer,))
    Room.objects.filter(pk=room.pk).update(member_count=3)

    result = services.repair_member_count(room.pk)

    room.refresh_from_db()
    assert room.member_count == 2
    assert result["checked"] == 1
    assert result["repaired"] == 1


def test_archive_room_archives_members(owner, peer):
    room = make_room(owner, members=(peer,))
    window_end = timezone.now()

    archived = services.archive_room(room.pk, window_end=window_end)

    assert archived.status == Room.Status.ARCHIVED
    assert archived.archived_at is not None
    assert not RoomMember.objects.filter(
        room=room, status=RoomMember.Status.ACTIVE
    ).exists()
    assert Notification.objects.filter(
        type=Notification.Type.ROOM_ARCHIVED, user__in=[owner, peer]
    ).count() == 2


def test_archive_room_is_idempotent_guard(owner):
    room = make_room(owner, status=Room.Status.ARCHIVED)

    with pytest.raises(Exception) as excinfo:
        services.archive_room(room.pk)

    assert getattr(excinfo.value, "error_code", "") == "INVALID_STATE"


def test_dissolve_room_clears_members(owner, peer):
    room = make_room(owner, members=(peer,))

    dissolved = services.dissolve_room(owner, room.pk)

    dissolved.refresh_from_db()
    assert dissolved.status == Room.Status.DISSOLVED
    assert dissolved.member_count == 0
    assert dissolved.dissolved_at is not None
    reasons = set(
        RoomMember.objects.filter(room=room).values_list("reason", "status")
    )
    assert reasons == {(RoomMember.Reason.DISSOLVED, RoomMember.Status.LEFT)}
    assert Notification.objects.filter(
        type=Notification.Type.ROOM_DISSOLVED, user__in=[owner, peer]
    ).count() == 2


def test_expired_window_blocks_lock(owner):
    TimeWindow.objects.filter(college=owner.college).update(
        start_at=timezone.now() - timedelta(hours=5),
        end_at=timezone.now() - timedelta(hours=4),
    )
    room = make_room(owner)

    with pytest.raises(WindowClosed):
        services.lock_room(owner, room.pk)

