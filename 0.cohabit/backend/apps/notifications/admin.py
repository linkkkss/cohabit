"""Admin 注册：站内信（docs/03 §1.7）。"""

from __future__ import annotations

from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "title", "read_at", "created_at")
    list_filter = ("type",)
    search_fields = ("user__uid", "user__nickname", "user__email", "title")
    raw_id_fields = ("user",)
    # 通知只增不改，创建时间由服务端写入。
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("user",)
