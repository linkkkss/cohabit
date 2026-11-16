"""Admin 导出隐私约束（docs/06 FA-08、S-03）。"""

from __future__ import annotations

import itertools

import pytest
from django.contrib import admin as django_admin
from django.test import RequestFactory

from apps.accounts.admin import UserAdmin
from apps.accounts.models import ContactInfo, User
from apps.adminops.models import AuditLog

pytestmark = pytest.mark.django_db

_UID = itertools.count(300)
PASSWORD = "Xk9#mQ2!zR7"


def make_user(email: str, *, nickname: str = "小满", **extra) -> User:
    values = {
        "uid": f"{next(_UID):010d}",
        "nickname": nickname,
        "gender": User.Gender.FEMALE,
        "grade": 2,
        "college": "计算机学院",
        "major": "软件工程",
    }
    values.update(extra)
    return User.objects.create_user(email=email, password=PASSWORD, **values)


def make_request(user: User):
    request = RequestFactory().post("/admin/accounts/user/")
    request.user = user
    request.META["HTTP_X_REQUEST_ID"] = "export-test"
    return request


def test_user_export_excludes_email_password_and_contact():
    admin = make_user("export-admin@stu.edu.cn", is_staff=True, is_superuser=True)
    target = make_user("secret-email@stu.edu.cn", nickname="隐私用户")
    ContactInfo.objects.filter(user=target).update(
        qq="987654321",
        wechat="secret-wechat",
        phone="13900139000",
    )
    model_admin = UserAdmin(User, django_admin.site)

    response = model_admin.export_users_csv(
        make_request(admin), User.objects.filter(pk=target.pk)
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert "users.csv" in response["Content-Disposition"]
    body = response.content.decode("utf-8-sig")
    header = body.splitlines()[0]
    assert target.uid in body
    assert "secret-email@stu.edu.cn" not in body
    assert "987654321" not in body
    assert "secret-wechat" not in body
    assert "13900139000" not in body
    assert "email" not in header
    assert "password" not in header
    assert "qq" not in header
    assert "wechat" not in header
    assert "phone" not in header
    assert AuditLog.objects.filter(
        action="AUDIT_EXPORTED", actor_id=admin.pk, request_id="export-test"
    ).exists()


def test_user_admin_registers_disable_and_export_actions():
    admin = make_user("action-admin@stu.edu.cn", is_staff=True, is_superuser=True)
    request = make_request(admin)
    model_admin = UserAdmin(User, django_admin.site)
    actions = model_admin.get_actions(request)
    assert "disable_users" in actions
    assert "export_users_csv" in actions
