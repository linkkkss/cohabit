"""M5-3 通知 Admin：只读浏览 + 已读筛选 + CSV 导出（docs/06 FA-08）。

导出列白名单只给 uid，不含邮箱/联系方式；导出动作本身写 ``AUDIT_EXPORTED``。
"""

from __future__ import annotations

import csv
import io

import pytest
from django.contrib import admin as django_admin
from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory
from django.utils import timezone

from apps.accounts.models import ContactInfo, User
from apps.adminops.models import AuditLog
from apps.notifications.admin import (
    NOTIFICATION_EXPORT_COLUMNS,
    NotificationAdmin,
    NotificationReadFilter,
)
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

QQ = "984120031"
WECHAT = "wx_notify_user"
PHONE = "13800004444"
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


def make_staff(*, uid: str = "0000000701", email: str = "notify-ops@cohabit.local"):
    staff = make_user(uid=uid, email=email, nickname="通知运营", role=User.Role.ADMIN)
    staff.is_staff = True
    staff.is_superuser = True
    staff.save(update_fields=["is_staff", "is_superuser"])
    return staff


def make_admin_request(user, *, request_id: str = "notify-ops"):
    request = RequestFactory().post("/admin/notifications/notification/", HTTP_X_REQUEST_ID=request_id)
    request.user = user
    request.session = {}
    return request


def make_notification(user: User, *, title: str, read: bool = False) -> Notification:
    return Notification.objects.create(
        user=user,
        type=Notification.Type.SYSTEM,
        title=title,
        payload={"reason": "TIMEOUT"},
        read_at=timezone.now() if read else None,
    )


def parse_csv(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_notification_admin_filters_and_read_filter():
    model_admin = NotificationAdmin(Notification, AdminSite())

    assert NotificationReadFilter in model_admin.list_filter
    assert ("created_at", django_admin.DateFieldListFilter) in model_admin.list_filter
    assert "type" in model_admin.list_filter
    assert "export_notifications_csv" in model_admin.actions
    staff = make_staff(uid="0000000705", email="ops705@cohabit.local")
    request = make_admin_request(staff)
    assert model_admin.readonly_fields == ("created_at",)
    assert model_admin.list_select_related == ("user",)
    assert model_admin.get_readonly_fields(request) == ("created_at",)


def test_read_filter_splits_read_and_unread():
    staff = make_staff()
    other = make_user(uid="0000000702", email="user702@stu.edu.cn", nickname="用户702")
    unread = make_notification(other, title="未读通知AAA")
    read = make_notification(other, title="已读通知BBB", read=True)
    request = RequestFactory().get("/admin/notifications/notification/", {"read": "unread"})
    request.user = staff
    request.session = {}
    model_admin = NotificationAdmin(Notification, AdminSite())

    unread_filter = NotificationReadFilter(
        request, {"read": ["unread"]}, Notification, model_admin
    )
    read_filter = NotificationReadFilter(
        request, {"read": ["read"]}, Notification, model_admin
    )

    unread_ids = set(unread_filter.queryset(request, Notification.objects.all()))
    read_ids = set(read_filter.queryset(request, Notification.objects.all()))
    assert unread_ids == {unread}
    assert read_ids == {read}
    assert [value for value, _ in unread_filter.lookups(request, model_admin)] == [
        "read",
        "unread",
    ]

    client = Client()
    client.force_login(staff)
    response = client.get("/admin/notifications/notification/", {"read": "unread"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "未读通知AAA" in content
    assert "已读通知BBB" not in content


def test_export_notifications_csv_whitelist_and_audit():
    staff = make_staff(uid="0000000703", email="ops703@cohabit.local")
    owner = make_user(uid="0000000704", email="user704@stu.edu.cn", nickname="用户704")
    seed_contact(owner, qq=QQ, wechat=WECHAT, phone=PHONE)
    notification = make_notification(owner, title="你的请求已关闭")
    model_admin = NotificationAdmin(Notification, AdminSite())

    response = model_admin.export_notifications_csv(
        make_admin_request(staff, request_id="notification-export"),
        Notification.objects.filter(pk=notification.pk),
    )

    rows = parse_csv(response)
    assert tuple(rows[0]) == NOTIFICATION_EXPORT_COLUMNS
    body = response.content.decode("utf-8-sig")
    assert owner.uid in body
    assert QQ not in body and WECHAT not in body and PHONE not in body
    assert not any(token in body.lower() for token in FORBIDDEN_TOKENS)
    audit = AuditLog.objects.get(action="AUDIT_EXPORTED", request_id="notification-export")
    assert audit.actor_id == staff.pk
    assert audit.meta == {
        "model": "Notification",
        "count": 1,
        "columns": list(NOTIFICATION_EXPORT_COLUMNS),
    }
