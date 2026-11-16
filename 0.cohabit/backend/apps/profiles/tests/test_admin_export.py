"""画像 Admin 导出隐私约束（docs/06 FA-08、S-03）。"""

from __future__ import annotations

import pytest
from django.contrib import admin as django_admin
from django.test import RequestFactory

from apps.accounts.models import ContactInfo, User
from apps.adminops.models import AuditLog
from apps.profiles.admin import ProfileAdmin
from apps.profiles.models import Profile

pytestmark = pytest.mark.django_db


def make_user(*, uid: str, email: str, nickname: str = "小明") -> User:
    return User.objects.create_user(
        uid=uid,
        email=email,
        password="Xk9#mQ2!zR7",
        nickname=nickname,
        gender="MALE",
        grade=2,
        college="计算机学院",
        major="软件工程",
    )


def test_profile_export_excludes_contact_details():
    admin = make_user(uid="3000000001", email="profile-admin@stu.edu.cn", nickname="管理员")
    admin.is_staff = True
    admin.is_superuser = True
    admin.save(update_fields=["is_staff", "is_superuser", "updated_at"])
    target = make_user(uid="3000000002", email="profile-user@stu.edu.cn", nickname="画像用户")
    Profile.objects.filter(user=target).update(
        tags=["早睡", "爱干净"], completeness=60
    )
    ContactInfo.objects.filter(user=target).update(
        qq="123456789",
        wechat="profile-secret-wx",
        phone="13700137000",
    )

    request = RequestFactory().post("/admin/profiles/profile/")
    request.user = admin
    request.META["HTTP_X_REQUEST_ID"] = "profile-export"
    model_admin = ProfileAdmin(Profile, django_admin.site)

    response = model_admin.export_profiles_csv(
        request, Profile.objects.filter(user=target)
    )

    assert response.status_code == 200
    assert "profiles.csv" in response["Content-Disposition"]
    body = response.content.decode("utf-8-sig")
    header = body.splitlines()[0]
    assert target.uid in body
    assert "早睡" in body
    assert "profile-user@stu.edu.cn" not in body
    assert "123456789" not in body
    assert "profile-secret-wx" not in body
    assert "13700137000" not in body
    for forbidden in ("email", "qq", "wechat", "phone", "password"):
        assert forbidden not in header
    assert AuditLog.objects.filter(
        action="AUDIT_EXPORTED", actor_id=admin.pk, request_id="profile-export"
    ).exists()
