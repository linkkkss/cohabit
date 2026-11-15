"""Admin 处理举报的测试（docs/03 §1.8 / docs/02 §9.2）。"""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from apps.accounts.models import User
from apps.adminops.admin import ReportAdmin
from apps.adminops.models import AuditLog, Report
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


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


def make_request(user):
    request = RequestFactory().post("/admin/adminops/report/")
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def make_report(reporter, status=Report.Status.OPEN):
    return Report.objects.create(
        reporter=reporter,
        target_type=Report.TargetType.USER,
        target_id=42,
        reason="言语不当（测试）",
        status=status,
    )


def test_admin_mark_resolved_sets_handler_and_audits():
    staff = make_user(uid="0000000099", email="admin@cohabit.local", role="ADMIN")
    reporter = make_user(
        uid="0000000007", email="demo007@stu.edu.cn", nickname="小算07"
    )
    report = make_report(reporter)
    model_admin = ReportAdmin(Report, AdminSite())
    request = make_request(staff)

    model_admin.mark_resolved(request, Report.objects.filter(pk=report.pk))

    report.refresh_from_db()
    assert report.status == Report.Status.RESOLVED
    assert report.handled_by_id == staff.pk
    audit = AuditLog.objects.get(action="REPORT_HANDLED", target_id=report.pk)
    assert audit.actor_id == staff.pk
    assert audit.target_type == AuditLog.TargetType.REPORT
    assert audit.meta == {
        "status": Report.Status.RESOLVED,
        "action_taken": Report.Status.RESOLVED,
    }
    note = Notification.objects.get(user=reporter, type=Notification.Type.SYSTEM)
    assert note.payload == {"report_id": report.pk, "status": Report.Status.RESOLVED}
    assert "举报处理结果" in note.title


def test_admin_mark_dismissed_skips_already_handled():
    staff = make_user(uid="0000000098", email="admin2@cohabit.local", role="ADMIN")
    reporter = make_user(
        uid="0000000019", email="demo019@stu.edu.cn", nickname="小算19"
    )
    report = make_report(reporter, status=Report.Status.RESOLVED)
    model_admin = ReportAdmin(Report, AdminSite())
    request = make_request(staff)

    model_admin.mark_dismissed(request, Report.objects.filter(pk=report.pk))

    report.refresh_from_db()
    assert report.status == Report.Status.RESOLVED
    assert report.handled_by_id is None
    assert not AuditLog.objects.filter(action="REPORT_HANDLED").exists()
    assert not Notification.objects.filter(user=reporter).exists()


def test_admin_report_is_read_only_with_actions():
    model_admin = ReportAdmin(Report, AdminSite())

    assert model_admin.has_add_permission(None) is False
    assert model_admin.has_delete_permission(None) is False
    assert {
        action.__name__
        for action in (model_admin.mark_resolved, model_admin.mark_dismissed)
    } == {
        "mark_resolved",
        "mark_dismissed",
    }
    assert "status" in model_admin.readonly_fields
    assert "handled_by" in model_admin.readonly_fields
