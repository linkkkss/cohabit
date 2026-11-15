"""Admin 注册：时间窗 / 举报 / 拉黑 / 审计（docs/03 §1.8）。"""

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone

from apps.core.audit import write_audit
from apps.notifications.services import notify

from .models import AuditLog, Block, Report, TimeWindow

_REPORT_STATUS_LABELS = {
    Report.Status.RESOLVED: "已处理",
    Report.Status.DISMISSED: "已驳回",
}


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
    list_filter = ("status", "target_type")
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
    )
    date_hierarchy = "created_at"
    actions = ("mark_resolved", "mark_dismissed")

    def has_add_permission(self, request) -> bool:
        # 举报由学生端提交，Admin 只处理不新增。
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.action(description="标记为已处理")
    def mark_resolved(self, request, queryset) -> None:
        self._handle(queryset, request, Report.Status.RESOLVED)

    @admin.action(description="标记为驳回")
    def mark_dismissed(self, request, queryset) -> None:
        self._handle(queryset, request, Report.Status.DISMISSED)

    def _handle(self, queryset, request, status: str) -> None:
        """处理举报：改状态 + 记录处理人，并写审计（docs/02 §9.2）。"""
        now = timezone.now()
        handled = 0
        for report in queryset:
            if report.status != Report.Status.OPEN:
                self.message_user(
                    request,
                    f"举报 #{report.pk} 已处理，跳过",
                    level=messages.WARNING,
                )
                continue
            report.status = status
            report.handled_by = request.user
            report.updated_at = now
            report.save(update_fields=["status", "handled_by", "updated_at"])
            write_audit(
                "REPORT_HANDLED",
                "report",
                report.pk,
                actor=request.user,
                meta={"status": status, "action_taken": status},
            )
            notify(
                report.reporter,
                "SYSTEM",
                {"report_id": report.pk, "status": status},
                title=f"举报处理结果：{_REPORT_STATUS_LABELS[status]}",
            )
            handled += 1
        if handled:
            self.message_user(request, f"已处理 {handled} 条举报")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("id", "blocker", "blocked", "created_at")
    search_fields = (
        "blocker__uid",
        "blocker__nickname",
        "blocked__uid",
        "blocked__nickname",
    )
    raw_id_fields = ("blocker", "blocked")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


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
    list_filter = ("target_type",)
    search_fields = ("action", "request_id", "actor__uid", "actor__nickname")
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

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
