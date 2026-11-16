"""M5-3 Admin 运营增强：举报筛选 / 联系方式审计 / 导出 / 审计筛选。

覆盖 docs/06 M5（FA-08、A-13、S-06、S-10、R-21）与 docs/02 §9.2–§9.3：

* 举报列表可按 status / target_type / 日期筛选，列表不批量展示联系方式；
* 举报详情页「查看目标联系方式」逐次写 ``ADMIN_VIEW_CONTACT``（只记 id，不记值）；
* 导出走显式列白名单 CSV，不出现 qq/wechat/phone/email/password/token，写
  ``AUDIT_EXPORTED``；
* 审计日志只读，支持 target_type / target_id / action / actor / 时间筛选。
"""

from __future__ import annotations

import csv
import io

import pytest
from django.contrib import admin as django_admin
from django.contrib.admin.sites import AdminSite
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client, RequestFactory
from django.utils import timezone

from apps.accounts.models import ContactInfo, User
from apps.adminops.admin import (
    AUDIT_EXPORT_COLUMNS,
    REPORT_EXPORT_COLUMNS,
    AuditLogAdmin,
    AuditTargetIdFilter,
    BlockAdmin,
    ReportAdmin,
)
from apps.adminops.models import AuditLog, Block, Report
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

QQ = "984120001"
WECHAT = "wx_ops_target"
PHONE = "13800001111"
# 导出列/内容里绝不允许出现的 token（docs/06 FA-08、docs/02 §1.7）。
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


def make_staff(*, uid: str = "0000000091", email: str = "ops@cohabit.local"):
    staff = make_user(uid=uid, email=email, nickname="运营", role=User.Role.ADMIN)
    staff.is_staff = True
    staff.is_superuser = True
    staff.save(update_fields=["is_staff", "is_superuser"])
    return staff


def make_scoped_staff(
    *, uid: str = "0000000190", email: str = "scoped@cohabit.local", grant: bool = True
):
    """能进 Admin 但只有 ``adminops.change_report`` 权限的运营（非 superuser）。

    ``grant=False`` 用于验证「能进 Admin 不等于能看联系方式」。
    """

    from django.contrib.auth.models import Permission

    staff = make_user(uid=uid, email=email, nickname="受限运营", role=User.Role.ADMIN)
    staff.is_staff = True
    staff.is_superuser = False
    staff.save(update_fields=["is_staff", "is_superuser"])
    if grant:
        permission = Permission.objects.get(
            content_type__app_label="adminops", codename="change_report"
        )
        staff.user_permissions.add(permission)
    return staff


def make_request(user, *, path: str = "/admin/adminops/report/", method: str = "post"):
    factory = getattr(RequestFactory(), method)
    request = factory(path)
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def make_export_request(user, *, request_id: str = "ops-export"):
    request = RequestFactory().post(
        "/admin/adminops/report/", HTTP_X_REQUEST_ID=request_id
    )
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def make_report(
    reporter: User,
    *,
    target_type: str = Report.TargetType.USER,
    target_id: int = 1,
    status: str = Report.Status.OPEN,
    reason: str = "言语不当（测试）",
) -> Report:
    return Report.objects.create(
        reporter=reporter,
        target_type=target_type,
        target_id=target_id,
        status=status,
        reason=reason,
    )


def parse_csv(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


# -- 举报：筛选 / 列表脱敏 ----------------------------------------------------


def test_report_admin_filters_actions_and_read_only():
    model_admin = ReportAdmin(Report, AdminSite())

    assert model_admin.date_hierarchy == "created_at"
    assert ("created_at", django_admin.DateFieldListFilter) in model_admin.list_filter
    assert "status" in model_admin.list_filter
    assert "target_type" in model_admin.list_filter
    assert "export_reports_csv" in model_admin.actions
    assert {"mark_resolved", "mark_dismissed"} <= set(model_admin.actions)
    assert "target_contacts" in model_admin.readonly_fields
    assert model_admin.has_add_permission(None) is False
    assert model_admin.has_delete_permission(None) is False


def test_report_changelist_filters_by_status_and_does_not_leak_contacts():
    staff = make_staff()
    open_reporter = make_user(
        uid="0000000101", email="open101@stu.edu.cn", nickname="小开101"
    )
    resolved_reporter = make_user(
        uid="0000000102", email="done102@stu.edu.cn", nickname="小结102"
    )
    target = make_user(uid="0000000103", email="target103@stu.edu.cn", nickname="目标103")
    seed_contact(target, qq=QQ, wechat=WECHAT, phone=PHONE)
    make_report(open_reporter, target_id=target.pk)
    make_report(resolved_reporter, target_id=target.pk, status=Report.Status.RESOLVED)

    client = Client()
    client.force_login(staff)
    response = client.get("/admin/adminops/report/", {"status": "OPEN"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "小开101" in content
    assert "小结102" not in content
    # 列表不批量展示 ContactInfo（docs/02 §9.2、X-50）。
    assert QQ not in content
    assert WECHAT not in content
    assert PHONE not in content


def test_report_changelist_supports_date_filter():
    staff = make_staff()
    reporter = make_user(uid="0000000104", email="date104@stu.edu.cn", nickname="小日104")
    make_report(reporter, target_id=1)
    today = timezone.localdate()
    client = Client()
    client.force_login(staff)

    response = client.get(
        "/admin/adminops/report/",
        {
            "created_at__year": today.year,
            "created_at__month": today.month,
            "created_at__day": today.day,
        },
    )

    assert response.status_code == 200
    assert "小日104" in response.content.decode()


# -- 举报详情：查看联系方式写审计 ---------------------------------------------


def test_contacts_view_audits_each_view_for_current_report_only():
    staff = make_staff()
    reporter = make_user(uid="0000000110", email="rep110@stu.edu.cn", nickname="举报人110")
    target = make_user(uid="0000000111", email="target111@stu.edu.cn", nickname="目标111")
    other = make_user(uid="0000000112", email="other112@stu.edu.cn", nickname="目标112")
    seed_contact(target, qq=QQ, wechat=WECHAT, phone=PHONE)
    seed_contact(other, qq="984120002", wechat="wx_other", phone="13800002222")
    report = make_report(reporter, target_id=target.pk)
    other_report = make_report(reporter, target_id=other.pk)

    client = Client()
    client.force_login(staff)
    url = f"/admin/adminops/report/{report.pk}/contacts/"

    first = client.get(url, HTTP_X_REQUEST_ID="contact-1")
    assert first.status_code == 200
    content = first.content.decode()
    assert QQ in content and WECHAT in content and PHONE in content
    assert "ADMIN_VIEW_CONTACT" in content

    audit = AuditLog.objects.get(action="ADMIN_VIEW_CONTACT")
    assert audit.actor_id == staff.pk
    assert audit.target_type == AuditLog.TargetType.USER
    assert audit.target_id == target.pk
    assert audit.request_id == "contact-1"
    # meta 只记 id，不记联系方式值（docs/02 §9.2）。
    assert audit.meta == {"target_user_id": target.pk, "report_id": report.pk}
    for value in (QQ, WECHAT, PHONE):
        assert value not in str(audit.meta)

    # 逐次查看都写审计。
    client.get(url)
    assert AuditLog.objects.filter(action="ADMIN_VIEW_CONTACT").count() == 2

    # 另一个举报单只对自身目标写审计。
    second = client.get(f"/admin/adminops/report/{other_report.pk}/contacts/")
    assert second.status_code == 200
    latest = AuditLog.objects.filter(action="ADMIN_VIEW_CONTACT").latest("pk")
    assert latest.target_id == other.pk
    assert latest.meta["report_id"] == other_report.pk


def test_contacts_view_resolves_room_and_connection_targets():
    from apps.connections.tests.helpers import make_connection
    from apps.rooms.tests.helpers import make_room

    staff = make_staff(uid="0000000113", email="ops113@cohabit.local")
    reporter = make_user(uid="0000000114", email="rep114@stu.edu.cn", nickname="举报114")
    owner = make_user(uid="0000000115", email="owner115@stu.edu.cn", nickname="房主115")
    member = make_user(uid="0000000116", email="member116@stu.edu.cn", nickname="成员116")
    seed_contact(owner, qq="984120003", wechat="wx_owner", phone="13800003333")
    seed_contact(member, qq="984120004", wechat="wx_member", phone="13800004444")
    room = make_room(owner, members=(member,))
    connection = make_connection(
        initiator=owner,
        target=member,
        type="INVITE",
    )
    room_report = make_report(reporter, target_type=Report.TargetType.ROOM, target_id=room.pk)
    connection_report = make_report(
        reporter, target_type=Report.TargetType.CONNECTION, target_id=connection.pk
    )

    client = Client()
    client.force_login(staff)

    room_response = client.get(f"/admin/adminops/report/{room_report.pk}/contacts/")
    assert room_response.status_code == 200
    assert "wx_owner" in room_response.content.decode()
    assert AuditLog.objects.filter(
        action="ADMIN_VIEW_CONTACT", target_id=owner.pk
    ).exists()

    AuditLog.objects.all().delete()
    connection_response = client.get(
        f"/admin/adminops/report/{connection_report.pk}/contacts/"
    )
    content = connection_response.content.decode()
    assert connection_response.status_code == 200
    assert "wx_owner" in content and "wx_member" in content
    assert AuditLog.objects.filter(action="ADMIN_VIEW_CONTACT").count() == 2


def test_contacts_view_404_for_missing_report():
    staff = make_staff(uid="0000000117", email="ops117@cohabit.local")
    client = Client()
    client.force_login(staff)

    response = client.get("/admin/adminops/report/999999/contacts/")

    assert response.status_code == 404
    assert not AuditLog.objects.filter(action="ADMIN_VIEW_CONTACT").exists()


def test_contacts_view_requires_change_report_permission():
    """能进 Admin 但无 change_report 权限 → 403，不写审计也不展示联系方式。"""

    staff = make_scoped_staff(grant=False)
    reporter = make_user(uid="0000000160", email="rep160@stu.edu.cn", nickname="举报160")
    target = make_user(uid="0000000161", email="target161@stu.edu.cn", nickname="目标161")
    seed_contact(target, qq=QQ, wechat=WECHAT, phone=PHONE)
    report = make_report(reporter, target_id=target.pk)

    client = Client()
    client.force_login(staff)
    response = client.get(
        f"/admin/adminops/report/{report.pk}/contacts/", HTTP_X_REQUEST_ID="denied-1"
    )

    assert response.status_code == 403
    content = response.content.decode()
    for value in (QQ, WECHAT, PHONE):
        assert value not in content
    assert not AuditLog.objects.filter(action="ADMIN_VIEW_CONTACT").exists()
    # 无权限的访问连状态都不该改变。
    assert Report.objects.get(pk=report.pk).status == Report.Status.OPEN


def test_contacts_view_allows_staff_with_change_report_permission():
    """仅有 change_report 权限（非 superuser）的运营可以查看并逐人写审计。"""

    staff = make_scoped_staff(uid="0000000162", email="scoped162@cohabit.local")
    reporter = make_user(uid="0000000163", email="rep163@stu.edu.cn", nickname="举报163")
    target = make_user(uid="0000000164", email="target164@stu.edu.cn", nickname="目标164")
    seed_contact(target, qq=QQ, wechat=WECHAT, phone=PHONE)
    report = make_report(reporter, target_id=target.pk)

    client = Client()
    client.force_login(staff)
    response = client.get(
        f"/admin/adminops/report/{report.pk}/contacts/", HTTP_X_REQUEST_ID="scoped-1"
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert QQ in content and WECHAT in content and PHONE in content
    audit = AuditLog.objects.get(action="ADMIN_VIEW_CONTACT")
    assert audit.actor_id == staff.pk
    assert audit.target_id == target.pk
    assert audit.request_id == "scoped-1"
    assert audit.meta == {"target_user_id": target.pk, "report_id": report.pk}


def test_report_detail_renders_contact_link_but_not_values():
    staff = make_staff(uid="0000000118", email="ops118@cohabit.local")
    reporter = make_user(uid="0000000119", email="rep119@stu.edu.cn", nickname="举报119")
    target = make_user(uid="0000000120", email="target120@stu.edu.cn", nickname="目标120")
    seed_contact(target, qq=QQ, wechat=WECHAT, phone=PHONE)
    report = make_report(reporter, target_id=target.pk)

    client = Client()
    client.force_login(staff)
    response = client.get(f"/admin/adminops/report/{report.pk}/change/")
    content = response.content.decode()

    assert response.status_code == 200
    assert f"/admin/adminops/report/{report.pk}/contacts/" in content
    assert QQ not in content
    assert PHONE not in content


# -- 导出：列白名单 + AUDIT_EXPORTED ------------------------------------------


def test_export_reports_csv_whitelist_and_audit():
    staff = make_staff(uid="0000000130", email="ops130@cohabit.local")
    reporter = make_user(uid="0000000131", email="rep131@stu.edu.cn", nickname="举报131")
    seed_contact(reporter, qq=QQ, wechat=WECHAT, phone=PHONE)
    make_report(reporter, target_id=42)
    model_admin = ReportAdmin(Report, AdminSite())

    response = model_admin.export_reports_csv(
        make_export_request(staff), Report.objects.all()
    )

    assert response["Content-Type"].startswith("text/csv")
    rows = parse_csv(response)
    assert tuple(rows[0]) == REPORT_EXPORT_COLUMNS
    body = response.content.decode("utf-8-sig")
    assert QQ not in body and WECHAT not in body and PHONE not in body
    assert not any(token in body.lower() for token in FORBIDDEN_TOKENS)
    assert "举报131" not in body  # 只导出 uid，不导出昵称
    audit = AuditLog.objects.get(action="AUDIT_EXPORTED")
    assert audit.actor_id == staff.pk
    assert audit.request_id == "ops-export"
    assert audit.meta == {
        "model": "Report",
        "count": 1,
        "columns": list(REPORT_EXPORT_COLUMNS),
    }


# -- 审计日志：筛选 / 只读 / 导出 ---------------------------------------------


def test_auditlog_admin_is_read_only_with_filters():
    model_admin = AuditLogAdmin(AuditLog, AdminSite())
    request = make_request(make_staff(uid="0000000140", email="ops140@cohabit.local"))

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False
    assert ("created_at", django_admin.DateFieldListFilter) in model_admin.list_filter
    assert ("actor", django_admin.RelatedOnlyFieldListFilter) in model_admin.list_filter
    assert AuditTargetIdFilter in model_admin.list_filter
    assert "action" in model_admin.list_filter
    assert "target_type" in model_admin.list_filter
    assert "export_audit_csv" in model_admin.actions


def test_auditlog_target_id_filter_matches_exact_target():
    model_admin = AuditLogAdmin(AuditLog, AdminSite())
    AuditLog.objects.create(action="CONNECTION_EXPIRED", target_type="CONNECTION", target_id=5)
    AuditLog.objects.create(action="REPORT_HANDLED", target_type="REPORT", target_id=7)
    request = RequestFactory().get("/admin/adminops/auditlog/", {"target_id": "5"})
    request.user = make_staff(uid="0000000141", email="ops141@cohabit.local")

    filter_instance = AuditTargetIdFilter(
        request, {"target_id": ["5"]}, AuditLog, model_admin
    )
    queryset = filter_instance.queryset(
        request, AuditLog.objects.filter(action__in=["CONNECTION_EXPIRED", "REPORT_HANDLED"])
    )

    assert list(queryset.values_list("target_id", flat=True)) == [5]
    assert [value for value, _ in filter_instance.lookups(request, model_admin)] == [
        "5",
        "7",
    ]


def test_auditlog_filter_by_action_and_actor():
    staff = make_staff(uid="0000000142", email="ops142@cohabit.local")
    other = make_user(uid="0000000143", email="other143@stu.edu.cn", nickname="他人143")
    AuditLog.objects.create(
        action="AUDIT_EXPORTED", target_type="USER", actor=staff, request_id="req-alpha"
    )
    AuditLog.objects.create(
        action="REPORT_HANDLED", target_type="REPORT", actor=other, request_id="req-beta"
    )
    client = Client()
    client.force_login(staff)

    # 筛选下拉里会渲染所有 action 文案，因此用唯一 request_id 判定命中行。
    by_action = client.get("/admin/adminops/auditlog/", {"action": "AUDIT_EXPORTED"})
    assert by_action.status_code == 200
    body = by_action.content.decode()
    assert "req-alpha" in body
    assert "req-beta" not in body

    by_actor = client.get(
        "/admin/adminops/auditlog/", {"actor__id__exact": str(other.pk)}
    )
    assert by_actor.status_code == 200
    body = by_actor.content.decode()
    assert "req-beta" in body
    assert "req-alpha" not in body


def test_export_audit_csv_whitelist_and_audit():
    staff = make_staff(uid="0000000144", email="ops144@cohabit.local")
    AuditLog.objects.create(
        action="REPORT_HANDLED",
        target_type="REPORT",
        target_id=9,
        actor=staff,
        meta={"status": "RESOLVED"},
        request_id="audit-1",
    )
    model_admin = AuditLogAdmin(AuditLog, AdminSite())

    response = model_admin.export_audit_csv(
        make_export_request(staff, request_id="audit-export"),
        AuditLog.objects.filter(action="REPORT_HANDLED"),
    )

    rows = parse_csv(response)
    assert tuple(rows[0]) == AUDIT_EXPORT_COLUMNS
    body = response.content.decode("utf-8-sig")
    assert "meta" not in rows[0]
    assert QQ not in body and PHONE not in body
    export_audit = AuditLog.objects.get(
        action="AUDIT_EXPORTED", request_id="audit-export"
    )
    assert export_audit.meta["model"] == "AuditLog"
    assert export_audit.meta["count"] == 1


def test_block_admin_has_date_filter():
    model_admin = BlockAdmin(Block, AdminSite())

    assert ("created_at", django_admin.DateFieldListFilter) in model_admin.list_filter


def test_export_action_is_registered_in_admin_actions():
    staff = make_staff(uid="0000000145", email="ops145@cohabit.local")
    model_admin = ReportAdmin(Report, AdminSite())
    request = make_request(staff)

    actions = model_admin.get_actions(request)

    assert "export_reports_csv" in actions
    assert actions["export_reports_csv"][2] == "导出所选举报 CSV（不含邮箱/联系方式）"
    # message 存储已被 action 使用过时不会抛错（FallbackStorage 冒烟）。
    assert get_messages(request) is not None


# -- 举报处理：状态 + 审计 + 通知同事务（S-10） --------------------------------


def test_handle_writes_status_audit_and_notification_together():
    staff = make_staff(uid="0000000170", email="ops170@cohabit.local")
    reporter = make_user(uid="0000000171", email="rep171@stu.edu.cn", nickname="举报171")
    report = make_report(reporter, target_id=88)
    model_admin = ReportAdmin(Report, AdminSite())
    request = RequestFactory().post(
        "/admin/adminops/report/", HTTP_X_REQUEST_ID="handle-1"
    )
    request.user = staff
    request.session = {}
    request._messages = FallbackStorage(request)

    model_admin.mark_resolved(request, Report.objects.filter(pk=report.pk))

    report.refresh_from_db()
    assert report.status == Report.Status.RESOLVED
    assert report.handled_by_id == staff.pk
    audit = AuditLog.objects.get(action="REPORT_HANDLED", target_id=report.pk)
    assert audit.actor_id == staff.pk
    assert audit.request_id == "handle-1"
    assert audit.meta == {"status": "RESOLVED", "action_taken": "RESOLVED"}
    notification = Notification.objects.get(user=reporter)
    assert notification.payload == {"report_id": report.pk, "status": "RESOLVED"}
    assert "已处理" in "".join(str(message) for message in get_messages(request))


def test_handle_rolls_back_report_when_audit_fails(monkeypatch):
    """审计写入失败时整条回滚：状态保持 OPEN、handled_by 空、无通知（S-10）。"""

    staff = make_staff(uid="0000000172", email="ops172@cohabit.local")
    reporter = make_user(uid="0000000173", email="rep173@stu.edu.cn", nickname="举报173")
    report = make_report(reporter, target_id=89)
    model_admin = ReportAdmin(Report, AdminSite())
    request = make_request(staff, path="/admin/adminops/report/")

    def boom(*args, **kwargs):
        raise RuntimeError("audit storage down")

    monkeypatch.setattr("apps.adminops.admin.write_audit", boom)

    model_admin.mark_resolved(request, Report.objects.filter(pk=report.pk))

    report.refresh_from_db()
    assert report.status == Report.Status.OPEN
    assert report.handled_by_id is None
    assert not Notification.objects.filter(user=reporter).exists()
    assert not AuditLog.objects.filter(action="REPORT_HANDLED").exists()
    notes = [str(message) for message in get_messages(request)]
    assert any("处理失败" in note and "已回滚" in note for note in notes)


def test_handle_skips_already_handled_reports():
    staff = make_staff(uid="0000000174", email="ops174@cohabit.local")
    reporter = make_user(uid="0000000175", email="rep175@stu.edu.cn", nickname="举报175")
    report = make_report(reporter, target_id=90, status=Report.Status.DISMISSED)
    model_admin = ReportAdmin(Report, AdminSite())
    request = make_request(staff, path="/admin/adminops/report/")

    model_admin.mark_resolved(request, Report.objects.filter(pk=report.pk))

    report.refresh_from_db()
    assert report.status == Report.Status.DISMISSED
    assert not AuditLog.objects.filter(action="REPORT_HANDLED").exists()
    notes = [str(message) for message in get_messages(request)]
    assert any("跳过" in note and "已处理" in note for note in notes)
