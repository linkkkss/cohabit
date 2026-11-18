"""rooms API 集成测试（docs/04 §4.3、docs/02 §4/§9/§10）。"""

from __future__ import annotations

import itertools
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.adminops.models import AuditLog, Block, TimeWindow
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.rooms import services
from apps.rooms.models import Room, RoomMember, RoomTransfer
from apps.rooms.tests.helpers import (
    add_member,
    auth_client,
    body,
    error_code,
    make_connection,
    make_room,
    make_user,
    open_window,
)

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
def stranger():
    return make_user(uid="1000000003", email="stranger@example.com", nickname="阿泽")


@pytest.fixture
def room(owner, member):
    return make_room(owner, members=(member,))


_seq = itertools.count(2_000_000_001, 2)


def fresh_room(**kwargs):
    """每个寝室配独立的房主/成员，避免 uq_user_active_room 冲突。"""
    base = next(_seq)
    owner = make_user(uid=str(base), email=f"o{base}@example.com", nickname="房主")
    peer = make_user(
        uid=str(base + 1), email=f"m{base}@example.com", nickname="室友"
    )
    room = make_room(owner, members=(peer,), **kwargs)
    return room, owner, peer


# --------------------------------------------------------------------------- #
# GET /api/rooms 广场
# --------------------------------------------------------------------------- #
def test_square_lists_recruiting_rooms_with_vacancy(stranger):
    visible, _, _ = fresh_room()
    full, _, _ = fresh_room(capacity=2, status=Room.Status.FULL)
    locked, _, _ = fresh_room(status=Room.Status.LOCKED)
    fresh_room(status=Room.Status.ARCHIVED)
    fresh_room(status=Room.Status.DISSOLVED, member_count=0)

    response = auth_client(stranger).get("/api/rooms")

    assert response.status_code == 200
    payload = body(response)
    codes = [item["code"] for item in payload["results"]]
    assert codes == [visible.code]
    assert full.code not in codes and locked.code not in codes
    assert payload["count"] == 1
    assert payload["next"] is None and payload["previous"] is None


def test_square_excludes_other_college_and_gender(owner, member):
    make_room(owner, members=(member,), college="外国语学院")
    other_gender = make_user(
        uid="1000000008",
        email="girl@example.com",
        nickname="小禾",
        gender="FEMALE",
    )
    make_room(other_gender, gender="FEMALE", college="计算机学院")
    viewer = make_user(uid="1000000009", email="viewer@example.com", nickname="小周")

    response = auth_client(viewer).get("/api/rooms")

    assert body(response)["count"] == 0


def test_square_filters_by_major_capacity_and_tags():
    target, _, _ = fresh_room(capacity=6, major="软件工程", tags=["早睡"])
    fresh_room(capacity=4, major="计算机科学", tags=["早睡"])
    fresh_room(capacity=6, major="软件工程", tags=["安静"])
    viewer = make_user(uid="1000000009", email="viewer@example.com", nickname="小周")
    client = auth_client(viewer)

    assert body(client.get("/api/rooms?major=软件工程"))["count"] == 2
    assert body(client.get("/api/rooms?capacity=6"))["count"] == 2
    combo = body(client.get("/api/rooms?major=软件工程&capacity=6&tags=早睡"))
    assert [row["code"] for row in combo["results"]] == [target.code]
    assert combo["results"][0]["tags"] == ["早睡"]


def test_square_excludes_rooms_user_has_left(owner, member, stranger):
    room = make_room(owner)
    add_member(room, stranger, status=RoomMember.Status.LEFT)

    response = auth_client(stranger).get("/api/rooms")

    assert body(response)["count"] == 0


def test_square_excludes_blocked_owner(owner, member, stranger):
    make_room(owner, members=(member,))
    Block.objects.create(blocker=stranger, blocked=owner)

    response = auth_client(stranger).get("/api/rooms")

    assert body(response)["count"] == 0
    assert Room.objects.count() == 1


def test_square_marks_can_apply_for_free_viewer(owner, member, stranger):
    make_room(owner, members=(member,))

    payload = body(auth_client(stranger).get("/api/rooms"))

    assert payload["results"][0]["can_apply"] is True
    assert payload["results"][0]["my_role"] is None


def test_square_can_apply_false_when_viewer_already_in_room(owner, member):
    make_room(owner, members=(member,), capacity=6)
    viewer = make_user(uid="1000000010", email="v@example.com", nickname="小周")
    partner = make_user(uid="1000000011", email="p@example.com", nickname="小何")
    make_room(viewer, members=(partner,), capacity=6)

    payload = body(auth_client(viewer).get("/api/rooms"))

    assert all(item["can_apply"] is False for item in payload["results"])


def test_square_rejects_invalid_capacity(owner, member):
    make_room(owner, members=(member,))

    response = auth_client(member).get("/api/rooms?capacity=3")

    assert response.status_code == 400
    assert error_code(response) == "CAPACITY_INVALID"


def test_square_requires_authentication(owner, member):
    make_room(owner, members=(member,))

    response = APIClient().get("/api/rooms")

    assert response.status_code == 401
    assert error_code(response) == "AUTH_REQUIRED"


def test_square_paginates_with_page_size(stranger):
    for _ in range(3):
        fresh_room()

    payload = body(auth_client(stranger).get("/api/rooms?page_size=2"))

    assert payload["count"] == 3
    assert len(payload["results"]) == 2
    assert payload["next"] is not None


def test_square_truncates_page_size_at_fifty(owner, member, stranger):
    make_room(owner, members=(member,))

    payload = body(auth_client(stranger).get("/api/rooms?page_size=500"))

    assert len(payload["results"]) == 1
    assert payload["count"] == 1


# --------------------------------------------------------------------------- #
# GET /api/rooms/mine
# --------------------------------------------------------------------------- #
def test_mine_without_room_returns_empty_shape(stranger):
    response = auth_client(stranger).get("/api/rooms/mine")

    assert response.status_code == 200
    assert body(response) == {
        "room": None,
        "pending_applications": [],
        "pending_transfer": None,
    }


def test_mine_returns_room_detail_for_member(room, member):
    payload = body(auth_client(member).get("/api/rooms/mine"))

    assert payload["room"]["code"] == room.code
    assert payload["room"]["my_role"] == RoomMember.Role.MEMBER
    assert payload["room"]["actions"]["can_leave"] is True
    assert payload["room"]["actions"]["can_lock"] is False
    assert payload["pending_applications"] == []


def test_mine_owner_sees_pending_applications(room, owner, stranger):
    make_connection(
        initiator=stranger,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    payload = body(auth_client(owner).get("/api/rooms/mine"))

    assert len(payload["pending_applications"]) == 1
    application = payload["pending_applications"][0]
    assert application["type"] == ConnectionRequest.Type.APPLY
    assert application["status"] == ConnectionRequest.Status.PENDING
    assert application["initiator"]["uid"] == stranger.uid
    assert "contact" not in application


def test_mine_non_owner_cannot_see_applications(room, member, stranger):
    make_connection(
        initiator=stranger,
        target=make_user(uid="1000000005", email="x@example.com", nickname="小徐"),
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    payload = body(auth_client(member).get("/api/rooms/mine"))

    assert payload["pending_applications"] == []


def test_mine_exposes_pending_transfer(room, owner, member):
    RoomTransfer.objects.create(
        room=room,
        from_owner=owner,
        to_member=member,
        status=RoomTransfer.Status.PENDING,
        expires_at=timezone.now() + timedelta(hours=24),
    )

    payload = body(auth_client(owner).get("/api/rooms/mine"))

    assert payload["pending_transfer"]["to_member"]["uid"] == member.uid
    assert payload["pending_transfer"]["status"] == RoomTransfer.Status.PENDING
    assert payload["room"]["actions"]["can_dissolve"] is True


# --------------------------------------------------------------------------- #
# GET /api/rooms/:code
# --------------------------------------------------------------------------- #
def test_detail_by_code(room, member):
    response = auth_client(member).get(f"/api/rooms/{room.code}")

    assert response.status_code == 200
    payload = body(response)
    assert payload["code"] == room.code
    assert payload["my_role"] == RoomMember.Role.MEMBER


def test_get_detail_by_id_is_not_allowed(room, member):
    response = auth_client(member).get(f"/api/rooms/{room.pk}")

    assert response.status_code == 404
    assert error_code(response) == "ROOM_NOT_FOUND"


def test_room_payloads_expose_internal_primary_key(room, owner, member, stranger):
    """F4 联调回归：列表/我的寝室/详情/公开页都返回内部 id（docs/04 §3.6）。"""
    square = body(auth_client(stranger).get("/api/rooms"))
    mine = body(auth_client(member).get("/api/rooms/mine"))
    detail_by_code = body(auth_client(member).get(f"/api/rooms/{room.code}"))
    detail_by_id = auth_client(member).get(f"/api/rooms/{room.pk}")
    public = body(APIClient().get(f"/api/public/rooms/{room.code}"))

    assert square["results"][0]["id"] == room.pk
    assert mine["room"]["id"] == room.pk
    assert detail_by_code["id"] == room.pk
    assert detail_by_id.status_code == 404
    assert public["id"] == room.pk


def test_detail_visible_to_same_college_and_gender_stranger(room, stranger):
    response = auth_client(stranger).get(f"/api/rooms/{room.code}")

    assert response.status_code == 200
    payload = body(response)
    assert payload["my_role"] is None
    assert payload["actions"]["can_lock"] is False


def test_detail_hidden_from_other_college(room, stranger):
    room.college = "外国语学院"
    room.save(update_fields=["college"])

    response = auth_client(stranger).get(f"/api/rooms/{room.code}")

    assert response.status_code == 404
    assert error_code(response) == "ROOM_NOT_FOUND"


def test_detail_hidden_from_other_gender(room, stranger):
    room.gender = "FEMALE"
    room.save(update_fields=["gender"])

    response = auth_client(stranger).get(f"/api/rooms/{room.code}")

    assert response.status_code == 404


def test_detail_hidden_for_archived_room_to_non_member(owner, member, stranger):
    room = make_room(owner, members=(member,), status=Room.Status.ARCHIVED)

    response = auth_client(stranger).get(f"/api/rooms/{room.code}")

    assert response.status_code == 404


def test_detail_members_only_include_active(room, owner, member):
    left = make_user(uid="1000000006", email="left@example.com", nickname="小离")
    removed = make_user(uid="1000000008", email="removed2@example.com", nickname="小退二")
    add_member(room, left, status=RoomMember.Status.LEFT)
    add_member(room, removed, status=RoomMember.Status.REMOVED)

    payload = body(auth_client(owner).get(f"/api/rooms/{room.code}"))

    uids = [row["uid"] for row in payload["members"]]
    assert member.uid in uids and owner.uid in uids
    assert left.uid not in uids
    assert removed.uid not in uids
    assert payload["actions"]["can_transfer"] is True
    assert body(auth_client(member).get(f"/api/rooms/{room.code}"))["actions"][
        "can_leave"
    ] is True


def test_detail_requires_authentication(room):
    response = APIClient().get(f"/api/rooms/{room.code}")

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# 终态寝室：原成员只读历史（docs/02 §4.8/§4.9/§4.10、X-48、W-09）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("terminal", [Room.Status.ARCHIVED, Room.Status.DISSOLVED])
def test_terminal_room_detail_read_only_for_former_member(room, owner, member, terminal):
    if terminal == Room.Status.ARCHIVED:
        services.archive_room(room.pk)
    else:
        services.dissolve_room(owner, room.pk)

    client = auth_client(member)
    by_code = client.get(f"/api/rooms/{room.code}")
    by_id = client.get(f"/api/rooms/{room.pk}")

    assert by_code.status_code == 200
    payload = body(by_code)
    assert payload["id"] == room.pk
    assert payload["code"] == room.code
    assert payload["status"] == terminal
    assert payload["my_role"] == RoomMember.Role.MEMBER
    assert all(value is False for value in payload["actions"].values())
    assert by_id.status_code == 404
    assert error_code(by_id) == "ROOM_NOT_FOUND"


def test_terminal_room_detail_hidden_from_non_member(room, stranger):
    services.archive_room(room.pk)

    response = auth_client(stranger).get(f"/api/rooms/{room.code}")

    assert response.status_code == 404
    assert error_code(response) == "ROOM_NOT_FOUND"


def test_terminal_room_detail_hidden_from_blocked_member(room, owner, member):
    services.archive_room(room.pk)
    Block.objects.create(blocker=owner, blocked=member)

    response = auth_client(member).get(f"/api/rooms/{room.code}")

    assert response.status_code == 404
    assert error_code(response) == "ROOM_NOT_FOUND"


def test_terminal_archived_room_detail_lists_full_member_roster(room, owner, member):
    services.archive_room(room.pk)
    removed = make_user(uid="1000000007", email="removed@example.com", nickname="小退")
    add_member(room, removed, status=RoomMember.Status.REMOVED)

    payload = body(auth_client(member).get(f"/api/rooms/{room.code}"))

    expected = list(
        RoomMember.objects.filter(room_id=room.pk)
        .select_related("user")
        .order_by("created_at", "id")
    )
    assert [row["uid"] for row in payload["members"]] == [
        row.user.uid for row in expected
    ]
    assert payload["members"][0]["role"] == RoomMember.Role.OWNER
    assert {row["status"] for row in payload["members"]} == {
        RoomMember.Status.ARCHIVED,
        RoomMember.Status.REMOVED,
    }
    assert payload["member_count"] == 2
    assert all(value is False for value in payload["actions"].values())


def test_terminal_dissolved_room_detail_lists_full_member_roster(room, owner, member):
    services.dissolve_room(owner, room.pk)

    payload = body(auth_client(member).get(f"/api/rooms/{room.code}"))

    assert {row["uid"] for row in payload["members"]} == {owner.uid, member.uid}
    assert {row["status"] for row in payload["members"]} == {RoomMember.Status.LEFT}
    assert {row["role"] for row in payload["members"]} == {
        RoomMember.Role.OWNER,
        RoomMember.Role.MEMBER,
    }
    assert payload["member_count"] == 0
    assert set(
        RoomMember.objects.filter(room_id=room.pk).values_list("reason", flat=True)
    ) == {RoomMember.Reason.DISSOLVED}


def test_open_room_hidden_from_former_member(room, member):
    services.leave_room(member, room.pk)

    response = auth_client(member).get(f"/api/rooms/{room.code}")
    mine = body(auth_client(member).get("/api/rooms/mine"))

    assert response.status_code == 404
    assert error_code(response) == "ROOM_NOT_FOUND"
    assert mine["room"] is None


@pytest.mark.parametrize("terminal", [Room.Status.ARCHIVED, Room.Status.DISSOLVED])
def test_mine_returns_terminal_room_history(room, owner, member, terminal):
    if terminal == Room.Status.ARCHIVED:
        services.archive_room(room.pk)
    else:
        services.dissolve_room(owner, room.pk)

    payload = body(auth_client(member).get("/api/rooms/mine"))

    assert payload["room"]["id"] == room.pk
    assert payload["room"]["status"] == terminal
    assert payload["room"]["my_role"] == RoomMember.Role.MEMBER
    assert {row["uid"] for row in payload["room"]["members"]} == {
        owner.uid,
        member.uid,
    }
    assert all(value is False for value in payload["room"]["actions"].values())
    assert payload["pending_applications"] == []
    assert payload["pending_transfer"] is None


def test_mine_prefers_most_recent_terminal_room(room, owner, member):
    services.archive_room(room.pk)
    other_owner = make_user(
        uid="1000000011", email="owner2@example.com", nickname="小满二号"
    )
    second = make_room(other_owner, members=(member,))
    services.dissolve_room(other_owner, second.pk)

    payload = body(auth_client(member).get("/api/rooms/mine"))

    assert payload["room"]["id"] == second.pk
    assert payload["room"]["status"] == Room.Status.DISSOLVED


# --------------------------------------------------------------------------- #
# PATCH /api/rooms/:id
# --------------------------------------------------------------------------- #
def test_patch_updates_title_and_writes_audit(room, owner):
    response = auth_client(owner).patch(
        f"/api/rooms/{room.pk}", {"title": "安静四人寝"}, format="json"
    )

    assert response.status_code == 200
    assert body(response)["title"] == "安静四人寝"
    assert body(response)["id"] == room.pk
    room.refresh_from_db()
    assert room.title == "安静四人寝"
    audit = AuditLog.objects.get(action="ROOM_UPDATED")
    assert audit.meta == {"fields": ["title"]}
    assert Notification.objects.count() == 0


def test_patch_updates_tags(room, owner):
    response = auth_client(owner).patch(
        f"/api/rooms/{room.pk}", {"tags": ["早睡", "安静"]}, format="json"
    )

    assert response.status_code == 200
    room.refresh_from_db()
    assert room.tags == ["早睡", "安静"]
    assert AuditLog.objects.get(action="ROOM_UPDATED").meta == {"fields": ["tags"]}


def test_patch_rejects_non_owner(room, member):
    response = auth_client(member).patch(
        f"/api/rooms/{room.pk}", {"title": "改名"}, format="json"
    )

    assert response.status_code == 403
    assert error_code(response) == "NOT_OWNER"


def test_patch_rejects_capacity(room, owner):
    response = auth_client(owner).patch(
        f"/api/rooms/{room.pk}", {"capacity": 6}, format="json"
    )

    assert response.status_code == 409
    assert error_code(response) == "CAPACITY_IMMUTABLE"


def test_patch_rejects_terminal_room(owner, member):
    room = make_room(owner, members=(member,), status=Room.Status.DISSOLVED, member_count=0)

    response = auth_client(owner).patch(
        f"/api/rooms/{room.pk}", {"title": "改名"}, format="json"
    )

    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"


def test_patch_rejects_empty_body(room, owner):
    response = auth_client(owner).patch(f"/api/rooms/{room.pk}", {}, format="json")

    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"


def test_patch_rejects_too_long_title(room, owner):
    response = auth_client(owner).patch(
        f"/api/rooms/{room.pk}", {"title": "长" * 31}, format="json"
    )

    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"


def test_patch_by_code_route_is_not_allowed(room, owner):
    response = auth_client(owner).patch(
        f"/api/rooms/{room.code}", {"title": "改名"}, format="json"
    )

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# lock / unlock
# --------------------------------------------------------------------------- #
def test_lock_closes_requests_and_notifies(room, owner, member, stranger):
    make_connection(
        initiator=stranger,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    response = auth_client(owner).post(f"/api/rooms/{room.pk}/lock")

    assert response.status_code == 200
    assert body(response)["status"] == Room.Status.LOCKED
    room.refresh_from_db()
    assert room.status == Room.Status.LOCKED
    assert Notification.objects.filter(type=Notification.Type.ROOM_LOCKED).count() == 2
    assert AuditLog.objects.filter(action="ROOM_LOCKED").exists()


def test_lock_requires_owner(room, member):
    response = auth_client(member).post(f"/api/rooms/{room.pk}/lock")

    assert response.status_code == 403
    assert error_code(response) == "NOT_OWNER"


def test_lock_twice_returns_invalid_state(room, owner):
    auth_client(owner).post(f"/api/rooms/{room.pk}/lock")

    response = auth_client(owner).post(f"/api/rooms/{room.pk}/lock")

    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"


def test_lock_requires_open_window(room, owner):
    TimeWindow.objects.filter(college=room.college).update(
        start_at=timezone.now() - timedelta(hours=4),
        end_at=timezone.now() - timedelta(hours=3),
    )

    response = auth_client(owner).post(f"/api/rooms/{room.pk}/lock")

    assert response.status_code == 409
    assert error_code(response) == "WINDOW_CLOSED"


def test_unlock_restores_recruiting_without_notification(room, owner):
    Room.objects.filter(pk=room.pk).update(status=Room.Status.LOCKED)

    response = auth_client(owner).post(f"/api/rooms/{room.pk}/unlock")

    assert response.status_code == 200
    assert body(response)["status"] == Room.Status.RECRUITING
    assert Notification.objects.count() == 0
    assert AuditLog.objects.filter(action="ROOM_UNLOCKED").exists()


def test_unlock_recruiting_room_returns_invalid_state(room, owner):
    response = auth_client(owner).post(f"/api/rooms/{room.pk}/unlock")

    assert response.status_code == 409
    assert error_code(response) == "INVALID_STATE"


# --------------------------------------------------------------------------- #
# leave / remove
# --------------------------------------------------------------------------- #
def test_member_leave_updates_row_and_count(room, member):
    response = auth_client(member).post(f"/api/rooms/{room.pk}/leave")

    assert response.status_code == 200
    room.refresh_from_db()
    row = RoomMember.objects.get(room=room, user=member)
    assert row.status == RoomMember.Status.LEFT
    assert row.reason == RoomMember.Reason.VOLUNTARY
    assert room.member_count == 1
    assert Notification.objects.filter(type=Notification.Type.MEMBER_LEFT).count() == 2


def test_member_leave_from_full_room_restores_recruiting(owner, member):
    room = make_room(owner, capacity=2, members=(member,), status=Room.Status.FULL)

    auth_client(member).post(f"/api/rooms/{room.pk}/leave")

    room.refresh_from_db()
    assert room.status == Room.Status.RECRUITING
    assert room.member_count == 1


def test_owner_leave_is_rejected(room, owner):
    response = auth_client(owner).post(f"/api/rooms/{room.pk}/leave")

    assert response.status_code == 409
    assert error_code(response) == "OWNER_MUST_TRANSFER_OR_DISSOLVE"


def test_non_member_leave_is_rejected(room, stranger):
    response = auth_client(stranger).post(f"/api/rooms/{room.pk}/leave")

    assert response.status_code == 403
    assert error_code(response) == "NOT_MEMBER"


def test_owner_removes_member(room, owner, member):
    response = auth_client(owner).delete(
        f"/api/rooms/{room.pk}/members/{member.uid}"
    )

    assert response.status_code == 200
    row = RoomMember.objects.get(room=room, user=member)
    assert row.status == RoomMember.Status.REMOVED
    assert row.reason == RoomMember.Reason.REMOVED_BY_OWNER
    assert AuditLog.objects.filter(action="MEMBER_REMOVED").exists()


def test_owner_cannot_remove_self(room, owner):
    response = auth_client(owner).delete(f"/api/rooms/{room.pk}/members/{owner.uid}")

    assert response.status_code == 409
    assert error_code(response) == "CANNOT_REMOVE_OWNER"


def test_member_cannot_remove_others(room, member, owner):
    response = auth_client(member).delete(f"/api/rooms/{room.pk}/members/{owner.uid}")

    assert response.status_code == 403
    assert error_code(response) == "NOT_OWNER"


def test_remove_unknown_uid_is_rejected(room, owner):
    response = auth_client(owner).delete(f"/api/rooms/{room.pk}/members/1999999999")

    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# dissolve
# --------------------------------------------------------------------------- #
def test_owner_dissolves_room(room, owner, member):
    response = auth_client(owner).post(f"/api/rooms/{room.pk}/dissolve")

    assert response.status_code == 200
    payload = body(response)
    assert payload["status"] == Room.Status.DISSOLVED
    assert payload["member_count"] == 0
    room.refresh_from_db()
    assert room.dissolved_at is not None
    assert not RoomMember.objects.filter(
        room=room, status=RoomMember.Status.ACTIVE
    ).exists()
    assert AuditLog.objects.filter(action="ROOM_DISSOLVED").exists()


def test_dissolve_closes_room_requests(room, owner, member, stranger):
    request = make_connection(
        initiator=stranger,
        target=owner,
        type=ConnectionRequest.Type.APPLY,
        room=room,
    )

    auth_client(owner).post(f"/api/rooms/{room.pk}/dissolve")

    request.refresh_from_db()
    assert request.status == ConnectionRequest.Status.CANCELLED
    assert request.close_reason == ConnectionRequest.CloseReason.ROOM_DISSOLVED


def test_non_owner_cannot_dissolve(room, member):
    response = auth_client(member).post(f"/api/rooms/{room.pk}/dissolve")

    assert response.status_code == 403
    assert error_code(response) == "NOT_OWNER"


def test_dissolve_twice_returns_room_dissolved(room, owner):
    auth_client(owner).post(f"/api/rooms/{room.pk}/dissolve")

    response = auth_client(owner).post(f"/api/rooms/{room.pk}/dissolve")

    assert response.status_code == 409
    assert error_code(response) == "ROOM_DISSOLVED"


# --------------------------------------------------------------------------- #
# 公开寝室页 / 无自助建房
# --------------------------------------------------------------------------- #
def test_public_room_is_anonymous_and_limited(room, owner, member):
    response = APIClient().get(f"/api/public/rooms/{room.code}")

    assert response.status_code == 200
    payload = body(response)
    assert payload["code"] == room.code
    assert payload["capacity"] == 4
    assert payload["college"] == room.college
    assert "uid" not in payload
    assert {row["nickname"] for row in payload["members"]} == {
        owner.nickname,
        member.nickname,
    }
    assert all("uid" not in row for row in payload["members"])
    assert "contact" not in str(payload)


def test_public_room_hidden_when_archived(owner, member):
    room = make_room(owner, members=(member,), status=Room.Status.ARCHIVED)

    response = APIClient().get(f"/api/public/rooms/{room.code}")

    assert response.status_code == 404
    assert error_code(response) == "ROOM_NOT_FOUND"


def test_public_room_hidden_when_dissolved(owner):
    room = make_room(owner, status=Room.Status.DISSOLVED, member_count=0)

    response = APIClient().get(f"/api/public/rooms/{room.code}")

    assert response.status_code == 404


def test_public_room_visible_when_locked(owner, member):
    room = make_room(owner, members=(member,), status=Room.Status.LOCKED)

    response = APIClient().get(f"/api/public/rooms/{room.code}")

    assert response.status_code == 200


def test_public_room_unknown_code_404():
    response = APIClient().get("/api/public/rooms/123456789")

    assert response.status_code == 404
    assert error_code(response) == "ROOM_NOT_FOUND"


def test_no_public_create_room_endpoint(stranger):
    response = auth_client(stranger).post("/api/rooms", {"capacity": 4}, format="json")

    assert response.status_code == 405
    assert Room.objects.count() == 0


def test_no_public_join_endpoint(room, stranger):
    response = auth_client(stranger).post(
        f"/api/rooms/{room.pk}/join", {}, format="json"
    )

    assert response.status_code == 404

