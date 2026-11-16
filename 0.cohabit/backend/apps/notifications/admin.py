"""Admin 注册：站内信（docs/03 §1.7、docs/02 §9.2）。

M5 Admin 运营增强：增加已读状态 / 日期筛选与 CSV 导出（白名单列，不含邮箱、
联系方式、payload 明细），导出动作写 ``AUDIT_EXPORTED``（docs/02 §9.3）。
"""

from __future__ import annotations

import csv

from django.contrib import admin
from django.http import HttpResponse

from apps.core.audit import write_audit

from .models import Notification

NOTIFICATION_EXPORT_COLUMNS = (
    "id",
    "user_uid",
    "type",
    "title",
    "read_at",
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


class NotificationReadFilter(admin.SimpleListFilter):
    title = "已读状态"
    parameter_name = "read"

    def lookups(self, request, model_admin):
        return (("read", "已读"), ("unread", "未读"))

    def queryset(self, request, queryset):
        value = self.value()
        if value == "read":
            return queryset.filter(read_at__isnull=False)
        if value == "unread":
            return queryset.filter(read_at__isnull=True)
        return queryset


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "title", "read_at", "created_at")
    list_filter = (
        "type",
        NotificationReadFilter,
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("user__uid", "user__nickname", "user__email", "title")
    raw_id_fields = ("user",)
    # 通知只增不改，创建时间由服务端写入。
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("user",)
    actions = ("export_notifications_csv",)

    @admin.action(description="导出所选站内信 CSV（不含邮箱/联系方式）")
    def export_notifications_csv(self, request, queryset):
        notes = queryset.select_related("user").order_by("pk")
        count = notes.count()
        rows = (
            (
                note.pk,
                note.user.uid if note.user_id else "",
                note.get_type_display(),
                note.title,
                _iso(note.read_at),
                _iso(note.created_at),
            )
            for note in notes.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "notification",
            None,
            actor=request.user,
            meta={
                "model": "Notification",
                "count": count,
                "columns": list(NOTIFICATION_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("notifications.csv", NOTIFICATION_EXPORT_COLUMNS, rows)
