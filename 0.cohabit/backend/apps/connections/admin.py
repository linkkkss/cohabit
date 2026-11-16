"""Admin 注册：组寝请求（docs/03 §1.6、docs/02 §9.2）。

M5 Admin 运营增强：

* 增加日期筛选与 CSV 导出（导出列白名单，不含联系方式）；
* **不提供 confirm / accept 一类 action**：Admin 不能代替学生确认（S-06），
  只能关闭 / 解散 / 禁用账号（docs/02 §10.2、docs/06 M5）。
"""

from __future__ import annotations

import csv

from django.contrib import admin
from django.http import HttpResponse

from apps.core.audit import write_audit

from .models import ConnectionRequest

CONNECTION_EXPORT_COLUMNS = (
    "id",
    "type",
    "initiator_uid",
    "target_uid",
    "room_code",
    "status",
    "close_reason",
    "expires_at",
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


@admin.register(ConnectionRequest)
class ConnectionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "initiator",
        "target",
        "room",
        "status",
        "close_reason",
        "expires_at",
        "created_at",
    )
    list_filter = (
        "type",
        "status",
        "close_reason",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "initiator__uid",
        "initiator__nickname",
        "target__uid",
        "target__nickname",
        "room__code",
        "message",
    )
    raw_id_fields = ("initiator", "target", "room", "closed_by")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    # S-06：这里只导出，不提供 confirm / accept 动作。
    actions = ("export_connections_csv",)

    @admin.action(description="导出所选组寝请求 CSV（不含联系方式）")
    def export_connections_csv(self, request, queryset):
        rows_qs = queryset.select_related("initiator", "target", "room").order_by("pk")
        count = rows_qs.count()
        rows = (
            (
                row.pk,
                row.get_type_display(),
                row.initiator.uid if row.initiator_id else "",
                row.target.uid if row.target_id else "",
                row.room.code if row.room_id else "",
                row.get_status_display(),
                row.get_close_reason_display() if row.close_reason else "",
                _iso(row.expires_at),
                _iso(row.created_at),
            )
            for row in rows_qs.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "connection",
            None,
            actor=request.user,
            meta={
                "model": "ConnectionRequest",
                "count": count,
                "columns": list(CONNECTION_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("connections.csv", CONNECTION_EXPORT_COLUMNS, rows)
