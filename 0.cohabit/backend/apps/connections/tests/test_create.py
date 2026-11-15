"""创建请求：守卫、限频、冷却与组合校验（docs/02 §3.2、docs/04 §4.4）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.adminops.models import AuditLog
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.rooms.models import RoomMember

from .helpers import (
    auth_client,
    block,
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


def _invite(client, target, **extra):
    payload = {"type": "INVITE", "target_uid": target.uid, "capacity_pref": 4}
    payload.update(extra)
    return client.post("/api/connections", payload, format="json")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_create_person_invite_returns_pending():
    actor, target = pair()
    open_window()

    response = _invite(auth_client(actor), target)

    assert response.status_code == 201
    payload = body(response)
    assert payload["type"] == "INVITE"
    assert payload["status"] == "PENDING"
    assert payload["direction"] == "sent"
    assert payload["room"] is None
    assert payload["contact"] == {}
    assert payload["contact_shared_at"] is None
    assert payload["version"] == 0
    expires_at = _parse(payload["expires_at"])
    assert abs(expires_at - (timezone.now() + timedelta(hours=48))) < timedelta(minutes=2)

    row = ConnectionRequest.objects.get(pk=payload["id"])
    assert row.initiator_id == actor.pk
    assert row.target_id == target.pk
    assert row.capacity_pref == 4
    note = Notification.objects.get(user=target, type=Notification.Type.CONNECTION_RECEIVED)
    assert note.payload["connection_id"] == row.pk
    assert note.payload["type"] == "INVITE"
    assert note.payload["from_nickname"] == actor.nickname
    audit = AuditLog.objects.get(action="CONNECTION_CREATED")
    assert audit.target_id == row.pk
    assert audit.meta["type"] == "INVITE"
    assert audit.meta["target_id"] == target.pk
    assert audit.meta["capacity_pref"] == 4


def test_create_requires_login():
    response = APIClient().post("/api/connections", {}, format="json")
    assert response.status_code == 401
    assert error_code(response) == "AUTH_REQUIRED"


def test_create_without_window_returns_window_closed():
    actor, target = pair()
    response = _invite(auth_client(actor), target)
    assert response.status_code == 409
    assert error_code(response) == "WINDOW_CLOSED"


def test_create_without_profile_returns_profile_incomplete():
    actor, target = pair(completeness=60)
    open_window()
    response = _invite(auth_client(actor), target)
    assert response.status_code == 409
    assert error_code(response) == "PROFILE_INCOMPLETE"
    assert body(response)["detail"]["completeness"] == 60


def test_create_when_target_profile_incomplete():
    actor, _ = pair()
    open_window()
    target = make_user()
    response = _invite(auth_client(actor), target)
    assert response.status_code == 409
    assert error_code(response) == "TARGET_PROFILE_INCOMPLETE"


def test_create_to_self_returns_self_request():
    actor, _ = pair()
    open_window()
    response = _invite(auth_client(actor), actor)
    assert response.status_code == 400
    assert error_code(response) == "SELF_REQUEST"


def test_create_cross_college_returns_wrong_college():
    actor, _ = pair()
    open_window()
    other = make_user(college="外国语学院")
    complete_profile(other)
    response = _invite(auth_client(actor), other)
    assert response.status_code == 403
    assert error_code(response) == "WRONG_COLLEGE"


def test_create_cross_gender_returns_wrong_gender():
    actor, _ = pair()
    open_window()
    other = make_user(gender="FEMALE")
    complete_profile(other)
    response = _invite(auth_client(actor), other)
    assert response.status_code == 403
    assert error_code(response) == "WRONG_GENDER"


def test_create_blocked_returns_blocked():
    actor, target = pair()
    open_window()
    block(target, actor)
    response = _invite(auth_client(actor), target)
    assert response.status_code == 403
    assert error_code(response) == "BLOCKED"


def test_create_when_initiator_in_room_returns_already_in_room():
    actor, target = pair()
    open_window()
    make_room(actor)
    response = _invite(auth_client(actor), target)
    assert response.status_code == 409
    assert error_code(response) == "ALREADY_IN_ROOM"


def test_create_when_target_in_room_returns_target_in_room():
    actor, target = pair()
    open_window()
    make_room(target)
    response = _invite(auth_client(actor), target)
    assert response.status_code == 409
    assert error_code(response) == "TARGET_IN_ROOM"


def test_create_unknown_target_returns_user_not_found():
    actor, _ = pair()
    open_window()
    missing = SimpleNamespace(uid="0599999999")
    response = _invite(auth_client(actor), missing)
    assert response.status_code == 404
    assert error_code(response) == "USER_NOT_FOUND"


def test_create_to_disabled_target_returns_user_not_found():
    actor, _ = pair()
    open_window()
    target = make_user(status="DISABLED")
    complete_profile(target)
    response = _invite(auth_client(actor), target)
    assert response.status_code == 404
    assert error_code(response) == "USER_NOT_FOUND"


def test_create_by_disabled_actor_returns_account_disabled():
    actor, target = pair()
    open_window()
    actor.status = "DISABLED"
    actor.save(update_fields=["status"])
    response = _invite(auth_client(actor), target)
    assert response.status_code == 403
    assert error_code(response) == "ACCOUNT_DISABLED"


def test_reverse_duplicate_returns_duplicate_request():
    actor, target = pair()
    open_window()
    assert _invite(auth_client(actor), target).status_code == 201

    response = _invite(auth_client(target), actor)

    assert response.status_code == 409
    assert error_code(response) == "DUPLICATE_REQUEST"
    assert ConnectionRequest.objects.filter(status__in=["PENDING"]).count() == 1


def test_in_flight_limit_returns_rate_limited():
    actor, _ = pair()
    open_window()
    for _ in range(3):
        other = make_user()
        complete_profile(other)
        make_connection(initiator=actor, target=other)
    fresh = make_user()
    complete_profile(fresh)

    response = _invite(auth_client(actor), fresh)

    assert response.status_code == 429
    assert error_code(response) == "RATE_LIMITED"


def test_daily_limit_returns_rate_limited():
    actor, _ = pair()
    open_window()
    now = timezone.now()
    for _ in range(10):
        other = make_user()
        complete_profile(other)
        row = make_connection(
            initiator=actor,
            target=other,
            status=ConnectionRequest.Status.CANCELLED,
            close_reason=ConnectionRequest.CloseReason.INITIATOR_CANCEL,
        )
        ConnectionRequest.objects.filter(pk=row.pk).update(created_at=now)
    fresh = make_user()
    complete_profile(fresh)

    response = _invite(auth_client(actor), fresh)

    assert response.status_code == 429
    assert error_code(response) == "RATE_LIMITED"


def test_cooldown_applies_both_directions():
    actor, target = pair()
    open_window()
    row = make_connection(
        initiator=target,
        target=actor,
        status=ConnectionRequest.Status.DECLINED,
        close_reason=ConnectionRequest.CloseReason.DECLINED,
    )
    ConnectionRequest.objects.filter(pk=row.pk).update(updated_at=timezone.now())

    forward = _invite(auth_client(actor), target)
    backward = _invite(auth_client(target), actor)

    assert forward.status_code == 429
    assert error_code(forward) == "COOLDOWN"
    assert backward.status_code == 429
    assert error_code(backward) == "COOLDOWN"


def test_apply_without_room_returns_invalid_type():
    actor, target = pair()
    open_window()
    response = auth_client(actor).post(
        "/api/connections",
        {"type": "APPLY", "target_uid": target.uid},
        format="json",
    )
    assert response.status_code == 400
    assert error_code(response) == "INVALID_TYPE"


def test_person_invite_with_room_returns_invalid_type():
    actor, target = pair()
    open_window()
    room = make_room(actor)
    response = _invite(auth_client(actor), target, room_id=room.pk)
    assert response.status_code == 400
    assert error_code(response) == "INVALID_TYPE"


def test_room_invite_with_capacity_returns_invalid_type():
    actor, target = pair()
    open_window()
    room = make_room(actor)
    response = _invite(auth_client(actor), target, room_id=room.pk, capacity_pref=4)
    assert response.status_code == 400
    assert error_code(response) == "INVALID_TYPE"


def test_person_invite_requires_capacity():
    actor, target = pair()
    open_window()
    response = auth_client(actor).post(
        "/api/connections",
        {"type": "INVITE", "target_uid": target.uid},
        format="json",
    )
    assert response.status_code == 400
    assert error_code(response) == "CAPACITY_INVALID"


def test_invalid_capacity_returns_capacity_invalid():
    actor, target = pair()
    open_window()
    response = _invite(auth_client(actor), target, capacity_pref=3)
    assert response.status_code == 400
    assert error_code(response) == "CAPACITY_INVALID"


def test_room_invite_by_non_owner_returns_invalid_target():
    actor, target = pair()
    open_window()
    owner = make_user()
    complete_profile(owner)
    room = make_room(owner)

    response = _invite(auth_client(actor), target, room_id=room.pk, capacity_pref=None)

    assert response.status_code == 400
    assert error_code(response) == "INVALID_TARGET"


def test_apply_to_non_owner_returns_invalid_target():
    actor, _ = pair()
    open_window()
    owner = make_user()
    complete_profile(owner)
    room = make_room(owner)
    not_owner = make_user()
    complete_profile(not_owner)

    response = auth_client(actor).post(
        "/api/connections",
        {"type": "APPLY", "target_uid": not_owner.uid, "room_id": room.pk},
        format="json",
    )

    assert response.status_code == 400
    assert error_code(response) == "INVALID_TARGET"


def test_room_invite_creates_request_with_room_code():
    actor, target = pair()
    open_window()
    room = make_room(actor)

    response = _invite(auth_client(actor), target, room_id=room.pk, capacity_pref=None)

    assert response.status_code == 201
    payload = body(response)
    assert payload["room"]["code"] == room.code
    row = ConnectionRequest.objects.get(pk=payload["id"])
    assert row.room_id == room.pk
    assert row.capacity_pref is None
    note = Notification.objects.get(user=target, type=Notification.Type.CONNECTION_RECEIVED)
    assert note.payload["room_code"] == room.code


def test_apply_creates_request_with_room():
    applicant, _ = pair()
    open_window()
    owner = make_user()
    complete_profile(owner)
    room = make_room(owner)

    response = auth_client(applicant).post(
        "/api/connections",
        {"type": "APPLY", "target_uid": owner.uid, "room_id": room.pk},
        format="json",
    )

    assert response.status_code == 201
    row = ConnectionRequest.objects.get(pk=body(response)["id"])
    assert row.type == "APPLY"
    assert row.room_id == room.pk
    assert row.initiator_id == applicant.pk


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("FULL", "ROOM_FULL"),
        ("LOCKED", "ROOM_LOCKED"),
        ("ARCHIVED", "ROOM_ARCHIVED"),
        ("DISSOLVED", "ROOM_DISSOLVED"),
    ],
)
def test_apply_to_unavailable_room_returns_room_error(status, expected):
    applicant, _ = pair()
    open_window()
    owner = make_user()
    complete_profile(owner)
    room = make_room(owner, status=status, member_count=1)

    response = auth_client(applicant).post(
        "/api/connections",
        {"type": "APPLY", "target_uid": owner.uid, "room_id": room.pk},
        format="json",
    )

    assert response.status_code == 409
    assert error_code(response) == expected


def test_message_too_long_returns_validation_error():
    actor, target = pair()
    open_window()
    response = _invite(auth_client(actor), target, message="x" * 201)
    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"


def test_target_uid_format_returns_validation_error():
    actor, _ = pair()
    open_window()
    response = auth_client(actor).post(
        "/api/connections",
        {"type": "INVITE", "target_uid": "123", "capacity_pref": 4},
        format="json",
    )
    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"


def _room_history(room, user, status=RoomMember.Status.LEFT) -> RoomMember:
    """为 ``(room,user)`` 造一条非 ACTIVE 历史（退出/被移除）。"""
    reason = (
        RoomMember.Reason.REMOVED_BY_OWNER
        if status == RoomMember.Status.REMOVED
        else RoomMember.Reason.VOLUNTARY
    )
    return RoomMember.objects.create(
        room=room,
        user=user,
        role=RoomMember.Role.MEMBER,
        status=status,
        reason=reason,
        left_at=timezone.now(),
    )


def test_apply_after_leaving_same_room_returns_rejoin_not_allowed():
    """R-13：退出后回原寝申请，创建时即 409 INVALID_STATE。"""
    applicant, _ = pair()
    open_window()
    owner = make_user()
    complete_profile(owner)
    room = make_room(owner)
    _room_history(room, applicant, RoomMember.Status.LEFT)

    response = auth_client(applicant).post(
        "/api/connections",
        {"type": "APPLY", "target_uid": owner.uid, "room_id": room.pk},
        format="json",
    )

    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"
    assert body(response)["detail"]["reason"] == "REJOIN_NOT_ALLOWED"
    assert ConnectionRequest.objects.count() == 0


def test_room_invite_for_removed_member_returns_rejoin_not_allowed():
    """R-13：房主邀请被移除过的成员，创建时即拒绝。"""
    owner, target = pair()
    open_window()
    room = make_room(owner)
    _room_history(room, target, RoomMember.Status.REMOVED)

    response = _invite(auth_client(owner), target, room_id=room.pk, capacity_pref=None)

    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"
    assert body(response)["detail"]["reason"] == "REJOIN_NOT_ALLOWED"
    assert ConnectionRequest.objects.count() == 0


def test_former_member_can_apply_to_another_room():
    """R-13 只封锁同一房间：历史成员仍可申请其他寝室。"""
    applicant, _ = pair()
    open_window()
    former_owner = make_user()
    complete_profile(former_owner)
    former_room = make_room(former_owner)
    _room_history(former_room, applicant, RoomMember.Status.LEFT)
    other_owner = make_user()
    complete_profile(other_owner)
    other_room = make_room(other_owner)

    response = auth_client(applicant).post(
        "/api/connections",
        {"type": "APPLY", "target_uid": other_owner.uid, "room_id": other_room.pk},
        format="json",
    )

    assert response.status_code == 201
    row = ConnectionRequest.objects.get(pk=body(response)["id"])
    assert row.room_id == other_room.pk
    assert row.status == ConnectionRequest.Status.PENDING


def test_owner_can_invite_former_member_of_another_room():
    """R-13 只封锁同一房间：可邀请别处退出/被移除的成员。"""
    owner, target = pair()
    open_window()
    other_owner = make_user()
    complete_profile(other_owner)
    other_room = make_room(other_owner)
    _room_history(other_room, target, RoomMember.Status.REMOVED)
    room = make_room(owner)

    response = _invite(auth_client(owner), target, room_id=room.pk, capacity_pref=None)

    assert response.status_code == 201
    row = ConnectionRequest.objects.get(pk=body(response)["id"])
    assert row.room_id == room.pk
    assert row.target_id == target.pk

