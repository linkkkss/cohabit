"""寝室路由解析回归：9 位 code 与内部 id 不得互相误吞（docs/04 §4.3）。"""

from __future__ import annotations

import pytest
from django.urls import resolve

from apps.rooms.tests.helpers import (
    auth_client,
    body,
    error_code,
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
    return make_user(uid="3000000001", email="route-owner@example.com", nickname="房主")


@pytest.fixture
def member():
    return make_user(uid="3000000002", email="route-member@example.com", nickname="成员")


@pytest.fixture
def room(owner, member):
    return make_room(owner, members=(member,))


def test_resolve_mine_before_code_and_id():
    match = resolve("/api/rooms/mine/")

    assert match.view_name == "rooms:mine"
    assert match.kwargs == {}


def test_resolve_nine_digit_path_to_code_route():
    match = resolve("/api/rooms/900000001/")

    assert match.view_name == "rooms:detail-by-code"
    assert match.kwargs == {"code": "900000001"}


def test_resolve_numeric_path_to_id_route():
    match = resolve("/api/rooms/7/")

    assert match.view_name == "rooms:detail"
    assert match.kwargs == {"room_id": "7"}


def test_resolve_action_and_public_routes():
    lock = resolve("/api/rooms/7/lock/")
    public = resolve("/api/public/rooms/900000001/")

    assert lock.view_name == "rooms:lock"
    assert lock.kwargs == {"room_id": "7"}
    assert public.view_name == "rooms:public"
    assert public.kwargs == {"code": "900000001"}


def test_resolve_supports_optional_trailing_slash():
    assert resolve("/api/rooms/mine").view_name == "rooms:mine"
    assert resolve("/api/rooms/900000001").view_name == "rooms:detail-by-code"


def test_get_detail_by_code_works_and_get_by_id_is_rejected(room, member):
    by_code = auth_client(member).get(f"/api/rooms/{room.code}")
    by_id = auth_client(member).get(f"/api/rooms/{room.pk}")

    assert by_code.status_code == 200
    assert body(by_code)["code"] == room.code
    assert by_id.status_code == 404
    assert error_code(by_id) == "ROOM_NOT_FOUND"


def test_patch_by_code_is_rejected_and_patch_by_id_works(room, owner):
    by_code = auth_client(owner).patch(
        f"/api/rooms/{room.code}", {"title": "改 code 不应生效"}, format="json"
    )
    by_id = auth_client(owner).patch(
        f"/api/rooms/{room.pk}", {"title": "按 id 修改"}, format="json"
    )

    assert by_code.status_code == 404
    assert by_id.status_code == 200
    assert body(by_id)["title"] == "按 id 修改"


def test_action_by_code_is_rejected_and_action_by_id_works(room, owner):
    by_code = auth_client(owner).post(f"/api/rooms/{room.code}/lock")
    by_id = auth_client(owner).post(f"/api/rooms/{room.pk}/lock")

    assert by_code.status_code == 404
    assert by_id.status_code == 200


def test_public_room_route_only_accepts_code(room):
    by_code = auth_client(room.owner).get(f"/api/public/rooms/{room.code}")
    by_id = auth_client(room.owner).get(f"/api/public/rooms/{room.pk}")

    assert by_code.status_code == 200
    assert by_id.status_code == 404
