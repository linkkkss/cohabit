"""M5-3 连接请求 Admin：只读观察 + CSV 导出，绝不代替学生确认（docs/06 S-06）。

Admin 只能关闭/解散/禁用，不能代替任一参与方确认或接受请求；因此
``ConnectionRequestAdmin`` 只有导出 action，没有 confirm/accept。
"""

from __future__ import annotations

import csv
import io
from datetime import timedelta

import pytest
from django.contrib import admin as django_admin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.exceptions import ApiError
from apps.accounts.models import ContactInfo, User
from apps.adminops.models import AuditLog
from apps.connections.admin import CONNECTION_EXPORT_COLUMNS, ConnectionRequestAdmin
from apps.connections.models import ConnectionRequest
from apps.connections import services as connection_services

pytestmark = pytest.mark.django_db

QQ = "984120021"
WECHAT = "wx_connection_target"
PHONE = "13800003333"
FORBIDDEN_TOKENS = ("qq", "wechat", "phone", "email", "password", "token")


def make_user(*, uid: str, email: str, nickname: str = "小满", role: str = "STUDENT"):
    return User.objects.create_user(
        uid=uid,
        email=email,
        password="Xk9#mQ2!zR7",
        nickname=nickname,
        gender="MALE",
        grade=2,
        college="计算机学院",
        major="软件工程",
        role=role,
        is_staff=role == User.Role.ADMIN,
    )


def seed_contact(user: User, *, qq: str = "", wechat: str = "", phone: str = "") -> ContactInfo:
    """User 创建时会自动建空 ContactInfo 行（profiles.signals），这里只回填值。"""

    contact, _ = ContactInfo.objects.update_or_create(
        user=user,
        defaults={"qq": qq or None, "wechat": wechat or None, "phone": phone or None},
    )
    return contact


def make_staff(*, uid: str = "0000000801", email: str = "conn-ops@cohabit.local"):
    staff = make_user(uid=uid, email=email, nickname="连接运营", role=User.Role.ADMIN)
    staff.is_staff = True
    staff.is_superuser = True
    staff.save(update_fields=["is_staff", "is_superuser"])
    return staff


def make_admin_request(user, *, request_id: str = "conn-ops"):
    request = RequestFactory().post("/admin/connections/connectionrequest/", HTTP_X_REQUEST_ID=request_id)
    request.user = user
    request.session = {}
    return request


def make_pair():
    initiator = make_user(uid="0000000802", email="init802@stu.edu.cn", nickname="发起802")
    target = make_user(uid="0000000803", email="target803@stu.edu.cn", nickname="目标803")
    connection = ConnectionRequest.objects.create(
        type=ConnectionRequest.Type.INVITE,
        initiator=initiator,
        target=target,
        status=ConnectionRequest.Status.PENDING,
        capacity_pref=4,
        expires_at=timezone.now() + timedelta(hours=12),
    )
    return initiator, target, connection


def parse_csv(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_admin_offers_export_only_no_confirm_or_accept():
    staff = make_staff()
    model_admin = ConnectionRequestAdmin(ConnectionRequest, AdminSite())
    request = make_admin_request(staff)

    actions = model_admin.get_actions(request)

    assert "export_connections_csv" in actions
    assert not any(
        word in name.lower()
        for name in actions
        for word in ("confirm", "accept", "share_contact")
    )
    assert ("created_at", django_admin.DateFieldListFilter) in model_admin.list_filter
    assert "type" in model_admin.list_filter
    assert "status" in model_admin.list_filter


def test_admin_cannot_confirm_on_behalf_of_students():
    staff = make_staff(uid="0000000804", email="ops804@cohabit.local")
    _, _, connection = make_pair()

    with pytest.raises(ApiError) as raised:
        connection_services.confirm_request(staff, connection.pk)

    assert raised.value.status_code in (403, 404)
    connection.refresh_from_db()
    assert connection.status == ConnectionRequest.Status.PENDING
    assert connection.version == 0


def test_export_connections_csv_whitelist_and_audit():
    staff = make_staff(uid="0000000805", email="ops805@cohabit.local")
    initiator, target, connection = make_pair()
    seed_contact(target, qq=QQ, wechat=WECHAT, phone=PHONE)
    model_admin = ConnectionRequestAdmin(ConnectionRequest, AdminSite())

    response = model_admin.export_connections_csv(
        make_admin_request(staff, request_id="connection-export"),
        ConnectionRequest.objects.filter(pk=connection.pk),
    )

    rows = parse_csv(response)
    assert tuple(rows[0]) == CONNECTION_EXPORT_COLUMNS
    body = response.content.decode("utf-8-sig")
    assert initiator.uid in body and target.uid in body
    assert QQ not in body and WECHAT not in body and PHONE not in body
    assert not any(token in body.lower() for token in FORBIDDEN_TOKENS)
    assert "发起802" not in body  # 只导出 uid，不含昵称
    audit = AuditLog.objects.get(action="AUDIT_EXPORTED", request_id="connection-export")
    assert audit.actor_id == staff.pk
    assert audit.meta == {
        "model": "ConnectionRequest",
        "count": 1,
        "columns": list(CONNECTION_EXPORT_COLUMNS),
    }
