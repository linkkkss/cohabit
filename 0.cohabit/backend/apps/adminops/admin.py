"""Admin 注册：时间窗 / 举报 / 拉黑 / 审计（docs/03 §1.8、docs/02 §9.2–§9.3）。

M5 Admin 运营增强：

* 举报处理保留 ``REPORT_HANDLED``；联系方式只在举报详情页点击查看时逐次写
  ``ADMIN_VIEW_CONTACT``，列表不批量展示、不提供批量导出（docs/02 §9.2、X-50）；
* 审计日志保持只读，支持 target_type / target_id / action / actor / 时间筛选；
* 导出统一走显式列白名单的 CSV（不含 email / 联系方式 / token 等），导出动作
  本身写 ``AUDIT_EXPORTED``（docs/02 §9.3、docs/03 §1.8.3）。
"""

from __future__ import annotations

import csv

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import escape, format_html

from apps.core.audit import write_audit
from apps.notifications.services import notify

from .models import AuditLog, Block, Report, TimeWindow

_REPORT_STATUS_LABELS = {
    Report.Status.RESOLVED: "已处理",
    Report.Status.DISMISSED: "已驳回",
}

# 导出白名单：不含 email / password / 联系方式 / token（docs/06 FA-08、S-03）。
REPORT_EXPORT_COLUMNS = (
    "id",
    "target_type",
    "target_id",
    "status",
    "reporter_uid",
    "handled_by_uid",
    "reason",
    "created_at",
)
AUDIT_EXPORT_COLUMNS = (
    "id",
    "action",
    "target_type",
    "target_id",
    "actor_uid",
    "request_id",
    "created_at",
)


def _csv_response(filename: str, header: tuple[str, ...], rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # Excel 中文兼容
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


def _request_id(request) -> str:
    value = request.headers.get("X-Request-Id") or request.META.get("HTTP_X_REQUEST_ID")
    return str(value or "")[:64]


def _iso(value) -> str:
    return value.isoformat() if value else ""


def _report_contact_users(report: Report):
    """解析举报目标对应的用户（用于 Admin 查看联系方式，docs/02 §9.2）。"""

    # 延迟导入，避免 admin 自动发现时的应用加载顺序问题。
    from apps.accounts.models import User
    from apps.connections.models import ConnectionRequest
    from apps.rooms.models import Room

    if report.target_type == Report.TargetType.USER:
        user = User.objects.filter(pk=report.target_id).first()
        return [user] if user is not None else []
    if report.target_type == Report.TargetType.ROOM:
        room = Room.objects.select_related("owner").filter(pk=report.target_id).first()
        return [room.owner] if room is not None else []
    if report.target_type == Report.TargetType.CONNECTION:
        row = (
            ConnectionRequest.objects.select_related("initiator", "target")
            .filter(pk=report.target_id)
            .first()
        )
        if row is None:
            return []
        return [row.initiator, row.target]
    return []


@admin.register(TimeWindow)
class TimeWindowAdmin(admin.ModelAdmin):
    list_display = ("college", "start_at", "end_at", "note", "updated_at")
    search_fields = ("college", "note")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "start_at"

    def has_delete_permission(self, request, obj=None) -> bool:
        # 时间窗不删除；只能改 end_at 提前/延长关窗（docs/03 §1.8.1）。
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "target_type",
        "target_id",
        "status",
        "handled_by",
        "created_at",
    )
    list_filter = (
        "status",
        "target_type",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("reporter__uid", "reporter__nickname", "reason")
    raw_id_fields = ("reporter", "handled_by")
    readonly_fields = (
        "reporter",
        "target_type",
        "target_id",
        "reason",
        "status",
        "handled_by",
        "created_at",
        "updated_at",
        "target_contacts",
    )
    date_hierarchy = "created_at"
    actions = ("mark_resolved", "mark_dismissed", "export_reports_csv")

    def has_add_permission(self, request) -> bool:
        # 举报由学生端提交，Admin 只处理不新增。
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    # -- 联系方式：仅详情页可点击查看，逐次审计（docs/02 §9.2、X-50） ----------

    def get_urls(self):
        custom = [
            path(
                "<path:object_id>/contacts/",
                self.admin_site.admin_view(self.contacts_view),
                name="adminops_report_contacts",
            ),
        ]
        return custom + super().get_urls()

    @admin.display(description="目标联系方式")
    def target_contacts(self, obj: Report | None):
        """详情页链接；列表不展示、不批量导出联系方式。"""

        if obj is None:
            return "保存后可用"
        url = reverse(
            f"{self.admin_site.name}:adminops_report_contacts", args=[obj.pk]
        )
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">查看目标联系方式（写审计）</a>',
            url,
        )

    def contacts_view(self, request, object_id: str):
        try:
            report_id = int(object_id)
        except (TypeError, ValueError):
            raise Http404("举报不存在")
        report = Report.objects.filter(pk=report_id).first()
        if report is None:
            raise Http404("举报不存在")

        # 查看联系方式属于举报处理动作：没有该举报的修改权限就不得读取/展示
        # 联系方式，也不写 ADMIN_VIEW_CONTACT 审计（docs/02 §9.2 权限矩阵）。
        if not self.has_change_permission(request, report):
            raise PermissionDenied("没有处理举报的权限，无法查看目标联系方式")

        request_id = _request_id(request)
        rows: list[str] = []
        for user in _report_contact_users(report):
            contact = getattr(user, "contact_info", None)
            # 每一次查看都写一条审计；meta 只记 id，不记联系方式值（docs/02 §9.2）。
            write_audit(
                "ADMIN_VIEW_CONTACT",
                "user",
                user.pk,
                actor=request.user,
                meta={"target_user_id": user.pk, "report_id": report.pk},
                request_id=request_id,
            )
            rows.append(
                "<tr>"
                f"<td>{escape(user.uid)}</td>"
                f"<td>{escape(user.nickname)}</td>"
                f"<td>{escape(contact.qq or '') if contact else ''}</td>"
                f"<td>{escape(contact.wechat or '') if contact else ''}</td>"
                f"<td>{escape(contact.phone or '') if contact else ''}</td>"
                "</tr>"
            )
        if not rows:
            rows.append('<tr><td colspan="5">目标已不存在或无可查看的联系方式</td></tr>')

        change_url = reverse(
            f"{self.admin_site.name}:adminops_report_change", args=[report.pk]
        )
        html = (
            "<!doctype html><html lang=\"zh-hans\"><head>"
            '<meta charset="utf-8"><title>举报目标联系方式</title></head><body>'
            f"<h1>举报 #{report.pk} 的目标联系方式</h1>"
            "<p>本次查看已写入审计事件 <code>ADMIN_VIEW_CONTACT</code>"
            f"（举报 #{report.pk}）。</p>"
            "<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\">"
            "<thead><tr><th>UID</th><th>昵称</th><th>QQ</th>"
            "<th>微信</th><th>手机号</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            f'<p><a href="{escape(change_url)}">返回举报详情</a></p>'
            "</body></html>"
        )
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Cache-Control"] = "no-store"
        return response

    # -- 举报处理（REPORT_HANDLED） --------------------------------------------

    @admin.action(description="标记为已处理")
    def mark_resolved(self, request, queryset) -> None:
        self._handle(queryset, request, Report.Status.RESOLVED)

    @admin.action(description="标记为驳回")
    def mark_dismissed(self, request, queryset) -> None:
        self._handle(queryset, request, Report.Status.DISMISSED)

    def _handle(self, queryset, request, status: str) -> None:
        """处理举报：改状态 + 记录处理人，并写审计（docs/02 §9.2）。

        每条举报单独一个事务：状态变更、``REPORT_HANDLED`` 审计、举报人通知必须
        同成同败（docs/02 §13.5 S-10），任一步失败则回滚该条并继续处理其余举报。
        """

        request_id = _request_id(request)
        handled = 0
        skipped = 0
        failed = 0
        for report_pk in list(queryset.values_list("pk", flat=True)):
            try:
                with transaction.atomic():
                    # 行锁重读，避免与另一个 Admin 并发处理同一条举报。
                    report = (
                        Report.objects.select_for_update().filter(pk=report_pk).first()
                    )
                    if report is None or report.status != Report.Status.OPEN:
                        skipped += 1
                        continue
                    report.status = status
                    report.handled_by = request.user
                    report.updated_at = timezone.now()
                    report.save(update_fields=["status", "handled_by", "updated_at"])
                    write_audit(
                        "REPORT_HANDLED",
                        "report",
                        report.pk,
                        actor=request.user,
                        meta={"status": status, "action_taken": status},
                        request_id=request_id,
                    )
                    notify(
                        report.reporter,
                        "SYSTEM",
                        {"report_id": report.pk, "status": status},
                        title=f"举报处理结果：{_REPORT_STATUS_LABELS[status]}",
                    )
                    handled += 1
            except Exception as exc:  # noqa: BLE001 - 逐条报告失败，事务已回滚
                failed += 1
                self.message_user(
                    request,
                    f"举报 #{report_pk} 处理失败（已回滚）：{exc}",
                    level=messages.ERROR,
                )
        if skipped:
            self.message_user(
                request,
                f"跳过 {skipped} 条已处理的举报",
                level=messages.WARNING,
            )
        if failed:
            self.message_user(
                request,
                f"共 {failed} 条举报处理失败",
                level=messages.ERROR,
            )
        if handled:
            self.message_user(request, f"已处理 {handled} 条举报")

    @admin.action(description="导出所选举报 CSV（不含邮箱/联系方式）")
    def export_reports_csv(self, request, queryset):
        reports = queryset.select_related("reporter", "handled_by").order_by("pk")
        count = reports.count()
        rows = (
            (
                report.pk,
                report.target_type,
                report.target_id,
                report.status,
                report.reporter.uid if report.reporter_id else "",
                report.handled_by.uid if report.handled_by_id else "",
                report.reason,
                _iso(report.created_at),
            )
            for report in reports.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "report",
            None,
            actor=request.user,
            meta={
                "model": "Report",
                "count": count,
                "columns": list(REPORT_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("reports.csv", REPORT_EXPORT_COLUMNS, rows)


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("id", "blocker", "blocked", "created_at")
    list_filter = (("created_at", admin.DateFieldListFilter),)
    search_fields = (
        "blocker__uid",
        "blocker__nickname",
        "blocked__uid",
        "blocked__nickname",
    )
    raw_id_fields = ("blocker", "blocked")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


class AuditTargetIdFilter(admin.SimpleListFilter):
    """按 target_id 精确筛选审计日志（distinct 值前 50 个，避免拖全表）。"""

    title = "目标 ID"
    parameter_name = "target_id"

    def lookups(self, request, model_admin):
        values = (
            AuditLog.objects.order_by()
            .exclude(target_id__isnull=True)
            .values_list("target_id", flat=True)
            .distinct()[:50]
        )
        return [(str(value), str(value)) for value in values]

    def queryset(self, request, queryset):
        value = self.value()
        if value and str(value).isdigit():
            return queryset.filter(target_id=int(value))
        return queryset


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "actor",
        "action",
        "target_type",
        "target_id",
        "request_id",
        "created_at",
    )
    list_filter = (
        "target_type",
        "action",
        AuditTargetIdFilter,
        ("actor", admin.RelatedOnlyFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "action",
        "request_id",
        "target_id",
        "actor__uid",
        "actor__nickname",
    )
    raw_id_fields = ("actor",)
    readonly_fields = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "meta",
        "request_id",
        "created_at",
    )
    date_hierarchy = "created_at"
    actions = ("export_audit_csv",)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.action(description="导出所选审计 CSV（不含 meta 明细）")
    def export_audit_csv(self, request, queryset):
        logs = queryset.select_related("actor").order_by("pk")
        count = logs.count()
        rows = (
            (
                log.pk,
                log.action,
                log.target_type,
                log.target_id,
                log.actor.uid if log.actor_id else "",
                log.request_id,
                _iso(log.created_at),
            )
            for log in logs.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "user",
            None,
            actor=request.user,
            meta={
                "model": "AuditLog",
                "count": count,
                "columns": list(AUDIT_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("audit_logs.csv", AUDIT_EXPORT_COLUMNS, rows)
