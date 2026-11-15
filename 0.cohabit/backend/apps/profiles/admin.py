"""画像 Admin（docs/03 §2.6：管理端只读查看，不手工改）。"""

from __future__ import annotations

from django.contrib import admin

from apps.profiles.models import Profile


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

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        # 只读详情：保留 change 页面用于查看，但保存按钮不产生修改。
        return True

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
