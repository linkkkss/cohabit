"""Admin 注册：组寝请求（docs/03 §1.6）。"""

from __future__ import annotations

from django.contrib import admin

from .models import ConnectionRequest


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
    list_filter = ("type", "status", "close_reason")
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
