"""Admin 注册：寝室 / 成员 / 房主转让（docs/03 §1.5、docs/02 §9.2）。

M5 Admin 运营增强：

* 增加日期筛选与 CSV 导出（导出列白名单，不含联系方式）；
* 提供「强制解散」action，复用 ``rooms.services.dissolve_room(force=True)``，
  审计事件为 ``ROOM_FORCE_DISSOLVED``（docs/02 §9.2）；
* R-21：有 ACTIVE 成员的寝室禁止直接删除，必须先解散
  （``MUST_DISSOLVE_BEFORE_DELETE``，docs/02 §9.2、docs/06 M5）。
"""

from __future__ import annotations

import csv

from django.contrib import admin, messages
from django.http import HttpResponse

from apps.core.audit import write_audit

from . import services
from .models import Room, RoomMember, RoomTransfer

# R-21 错误码：Admin 不能直接删除还有成员的寝室，必须先走解散（docs/02 §9.2）。
MUST_DISSOLVE_BEFORE_DELETE = "MUST_DISSOLVE_BEFORE_DELETE"

# 导出白名单：不含 email / password / ContactInfo（docs/06 FA-08、S-03）。
ROOM_EXPORT_COLUMNS = (
    "code",
    "title",
    "owner_uid",
    "capacity",
    "member_count",
    "gender",
    "college",
    "major",
    "status",
    "created_at",
)
ROOM_MEMBER_EXPORT_COLUMNS = (
    "id",
    "room_code",
    "user_uid",
    "role",
    "status",
    "reason",
    "left_at",
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


def _has_active_members(room: Room) -> bool:
    return room.members.filter(status=RoomMember.Status.ACTIVE).exists()


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
    list_filter = (
        "status",
        "capacity",
        "gender",
        "college",
        ("created_at", admin.DateFieldListFilter),
    )
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
    actions = ("force_dissolve_rooms", "export_rooms_csv")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields
        return ("code", *self.readonly_fields)

    # -- R-21：有成员的寝室必须先解散才能删除 ---------------------------------

    def has_delete_permission(self, request, obj=None) -> bool:
        # 有 ACTIVE 成员时不允许直接删除（R-21）。这里只返回 False、不写 message：
        # Admin 渲染 change 页就会调用本方法，写 message 会让每次打开寝室详情都
        # 弹出「请先解散」的错误提示。真正的拒绝提示在 delete_model /
        # delete_queryset 里给出。
        if obj is not None and _has_active_members(obj):
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj) -> None:
        if _has_active_members(obj):
            self.message_user(
                request,
                f"寝室 {obj.code} 仍有成员，请先解散（{MUST_DISSOLVE_BEFORE_DELETE}）。",
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset) -> None:
        rooms = list(queryset)
        blocked = [room for room in rooms if _has_active_members(room)]
        if blocked:
            codes = "、".join(room.code for room in blocked[:10])
            self.message_user(
                request,
                f"以下寝室仍有成员，请先解散（{MUST_DISSOLVE_BEFORE_DELETE}）：{codes}",
                level=messages.ERROR,
            )
        allowed_pks = [room.pk for room in rooms if room not in blocked]
        if allowed_pks:
            super().delete_queryset(request, Room.objects.filter(pk__in=allowed_pks))

    # -- 强制解散（复用服务层，写 ROOM_FORCE_DISSOLVED 审计） ------------------

    @admin.action(description="强制解散所选寝室（写 ROOM_FORCE_DISSOLVED 审计）")
    def force_dissolve_rooms(self, request, queryset) -> None:
        request_id = _request_id(request)
        dissolved = 0
        for room in queryset.order_by("pk"):
            try:
                services.dissolve_room(
                    request.user,
                    room.pk,
                    reason="ADMIN_FORCE",
                    force=True,
                    request_id=request_id,
                )
            except Exception as exc:  # noqa: BLE001 - 后台批量动作逐条报告失败
                self.message_user(
                    request,
                    f"寝室 {room.code} 解散失败：{exc}",
                    level=messages.ERROR,
                )
                continue
            dissolved += 1
        if dissolved:
            self.message_user(request, f"已强制解散 {dissolved} 个寝室。")

    # -- 导出（显式列白名单 + AUDIT_EXPORTED） --------------------------------

    @admin.action(description="导出所选寝室 CSV（不含联系方式）")
    def export_rooms_csv(self, request, queryset):
        rooms = queryset.select_related("owner").order_by("pk")
        count = rooms.count()
        rows = (
            (
                room.code,
                room.title,
                room.owner.uid if room.owner_id else "",
                room.capacity,
                room.member_count,
                room.get_gender_display(),
                room.college,
                room.major,
                room.get_status_display(),
                _iso(room.created_at),
            )
            for room in rooms.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "room",
            None,
            actor=request.user,
            meta={
                "model": "Room",
                "count": count,
                "columns": list(ROOM_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("rooms.csv", ROOM_EXPORT_COLUMNS, rows)


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
    list_filter = (
        "role",
        "status",
        "reason",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("room__code", "user__uid", "user__nickname")
    raw_id_fields = ("room", "user")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    actions = ("export_room_members_csv",)

    @admin.action(description="导出所选寝室成员 CSV（不含联系方式）")
    def export_room_members_csv(self, request, queryset):
        members = queryset.select_related("room", "user").order_by("pk")
        count = members.count()
        rows = (
            (
                member.pk,
                member.room.code if member.room_id else "",
                member.user.uid if member.user_id else "",
                member.get_role_display(),
                member.get_status_display(),
                member.get_reason_display(),
                _iso(member.left_at),
                _iso(member.created_at),
            )
            for member in members.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "room_member",
            None,
            actor=request.user,
            meta={
                "model": "RoomMember",
                "count": count,
                "columns": list(ROOM_MEMBER_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("room_members.csv", ROOM_MEMBER_EXPORT_COLUMNS, rows)


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
    list_filter = ("status", ("created_at", admin.DateFieldListFilter))
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
