"""Admin 注册：时间窗 / 举报 / 拉黑 / 审计（docs/03 §1.8）。"""

from __future__ import annotations

from django.contrib import admin

from .models import AuditLog, Block, Report, TimeWindow


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
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        # 举报由学生端提交，Admin 只处理不新增。
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


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
