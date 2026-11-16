"""画像 Admin（docs/03 §2.6：管理端只读查看，不手工改）。"""

from __future__ import annotations

import csv
import json

from django.contrib import admin
from django.http import HttpResponse

from apps.core.audit import write_audit
from apps.profiles.models import Profile

# 导出白名单：画像本身不含联系方式（docs/06 FA-08、S-03）。
PROFILE_EXPORT_COLUMNS = (
    "uid",
    "nickname",
    "completeness",
    "questionnaire_version",
    "tags",
    "updated_at",
)


def _csv_response(filename: str, header: tuple[str, ...], rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


def _request_id(request) -> str:
    value = request.headers.get("X-Request-Id") or request.META.get("HTTP_X_REQUEST_ID")
    return str(value or "")[:64]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "completeness",
        "questionnaire_version",
        "updated_at",
    )
    list_select_related = ("user",)
    search_fields = ("user__uid", "user__email", "user__nickname")
    readonly_fields = (
        "user",
        "hard_answers",
        "soft_answers",
        "red_lines",
        "red_lines_confirmed",
        "tags",
        "prompts",
        "dims",
        "completeness",
        "questionnaire_version",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)
    actions = ("export_profiles_csv",)

    @admin.action(description="导出所选画像 CSV（不含联系方式）")
    def export_profiles_csv(self, request, queryset):
        profiles = queryset.select_related("user").order_by("pk")
        rows = (
            (
                profile.user.uid,
                profile.user.nickname,
                profile.completeness,
                profile.questionnaire_version,
                json.dumps(profile.tags, ensure_ascii=False),
                profile.updated_at.isoformat() if profile.updated_at else "",
            )
            for profile in profiles.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "user",
            None,
            actor=request.user,
            meta={
                "model": "Profile",
                "count": profiles.count(),
                "columns": list(PROFILE_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("profiles.csv", PROFILE_EXPORT_COLUMNS, rows)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        # 只读详情：保留 change 页面用于查看，但保存按钮不产生修改。
        return True

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
