"""Admin 注册：寝室 / 成员 / 房主转让（docs/03 §1.5）。"""

from __future__ import annotations

from django.contrib import admin

from .models import Room, RoomMember, RoomTransfer


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "owner",
        "capacity",
        "member_count",
        "gender",
        "college",
        "status",
        "created_at",
    )
    list_filter = ("status", "capacity", "gender", "college")
    search_fields = (
        "code",
        "title",
        "owner__uid",
        "owner__nickname",
        "college",
        "major",
    )
    raw_id_fields = ("owner",)
    # 寝室号由服务端生成；member_count 由服务层维护，Admin 不直接改。
    # 仅新增时允许手填 9 位寝室号（Admin 补建场景），修改时只读。
    readonly_fields = ("member_count", "created_at", "updated_at")
    date_hierarchy = "created_at"

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields
        return ("code", *self.readonly_fields)


@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "user",
        "role",
        "status",
        "reason",
        "left_at",
        "created_at",
    )
    list_filter = ("role", "status", "reason")
    search_fields = ("room__code", "user__uid", "user__nickname")
    raw_id_fields = ("room", "user")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(RoomTransfer)
class RoomTransferAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "from_owner",
        "to_member",
        "status",
        "expires_at",
        "decided_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "room__code",
        "from_owner__uid",
        "from_owner__nickname",
        "to_member__uid",
        "to_member__nickname",
    )
    raw_id_fields = ("room", "from_owner", "to_member")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
