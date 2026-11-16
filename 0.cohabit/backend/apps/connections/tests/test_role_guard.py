"""学生端写操作角色守卫（docs/02 §1.1 第 2 步、docs/06 S-06/S-14）。"""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.connections.models import ConnectionRequest

from .helpers import (
    PASSWORD,
    auth_client,
    body,
    complete_profile,
    make_connection,
    open_window,
    pair,
)

pytestmark = pytest.mark.django_db


def _admin() -> User:
    """ADMIN + staff：学生端写动作必须被守卫拒绝，读取不受影响。"""
    return User.objects.create_superuser(
        uid="1999999001",
        email="role-admin@example.com",
        password=PASSWORD,
        nickname="管理员",
        gender="MALE",
        grade=2,
        college="计算机学院",
        major="软件工程",
    )


def test_admin_accept_is_forbidden_before_service():
    initiator, target = pair()
    open_window()
    row = make_connection(initiator=initiator, target=target, capacity_pref=4)

    response = auth_client(_admin()).post(f"/api/connections/{row.pk}/accept")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert "学生" in response.json()["message"]
    row.refresh_from_db()
    assert row.status == ConnectionRequest.Status.PENDING


def test_admin_confirm_is_forbidden():
    initiator, target = pair()
    open_window()
    row = make_connection(initiator=initiator, target=target, capacity_pref=4)

    response = auth_client(_admin()).post(f"/api/connections/{row.pk}/confirm")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    row.refresh_from_db()
    assert row.status == ConnectionRequest.Status.PENDING


def test_admin_unknown_connection_returns_403_not_404():
    """权限守卫先于 service，Admin 不能借不存在 id 探测 404。"""
    response = auth_client(_admin()).post("/api/connections/999999/accept")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_admin_cannot_create_connection():
    initiator, target = pair()
    open_window()

    response = auth_client(_admin()).post(
        "/api/connections",
        {"type": "INVITE", "target_uid": target.uid, "capacity_pref": 4},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert ConnectionRequest.objects.filter(initiator=initiator).count() == 0


def test_student_accept_and_confirm_still_work():
    initiator, target = pair()
    open_window()
    row = make_connection(initiator=initiator, target=target, capacity_pref=4)

    accept = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert accept.status_code == 200
    assert body(accept)["status"] == ConnectionRequest.Status.CONTACT_SHARED

    confirm = auth_client(initiator).post(f"/api/connections/{row.pk}/confirm")
    assert confirm.status_code == 200
    assert body(confirm)["status"] == ConnectionRequest.Status.CONFIRMING


def test_admin_can_read_connection_list_and_detail():
    initiator, _ = pair()
    admin = _admin()
    complete_profile(admin)
    row = make_connection(initiator=initiator, target=admin, capacity_pref=4)
    client = auth_client(admin)

    listing = client.get("/api/connections")
    assert listing.status_code == 200
    assert body(listing)["count"] == 1

    detail = client.get(f"/api/connections/{row.pk}")
    assert detail.status_code == 200
    assert body(detail)["id"] == row.pk
