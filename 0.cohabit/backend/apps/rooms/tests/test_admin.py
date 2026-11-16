"""M5-3 寝室 Admin：强制解散、R-21 删除保护、CSV 导出（docs/06 R-21、S-10、FA-08）。

* 强制解散复用 ``rooms.services.dissolve_room(force=True)``，写
  ``ROOM_FORCE_DISSOLVED`` 审计、成员 LEFT、请求 ROOM_DISSOLVED、双方通知；
* 有 ACTIVE 成员的寝室禁止删除（R-21：先解散），``delete_model`` /
  ``delete_queryset`` 都不落库；
* 导出走显式列白名单，不含 ContactInfo / qq / wechat / phone，写 AUDIT_EXPORTED。
"""

from __future__ import annotations

import csv
import io
from datetime import timedelta

import pytest
from django.contrib import admin as django_admin
from django.contrib.admin.sites import AdminSite
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client, RequestFactory
from django.utils import timezone

from apps.accounts.models import ContactInfo, User
from apps.adminops.models import AuditLog
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.rooms.admin import (
    MUST_DISSOLVE_BEFORE_DELETE,
    ROOM_EXPORT_COLUMNS,
    ROOM_MEMBER_EXPORT_COLUMNS,
    RoomAdmin,
    RoomMemberAdmin,
    RoomTransferAdmin,
)
from apps.rooms.models import Room, RoomMember, RoomTransfer

from .helpers import next_room_code, open_window

pytestmark = pytest.mark.django_db

QQ = "984120011"
WECHAT = "wx_room_owner"
PHONE = "13800002222"
FORBIDDEN_TOKENS = ("qq", "wechat", "phone", "email", "password", "token")


def make_user(*, uid: str, email: str, nickname: str = "小满", role: str = "STUDENT"):
    return User.objects.create_user(
        uid=uid,
        email=email,
        password="Xk9#mQ2!zR7",
        nickname=nickname,
        gender="MALE",
        grade=2,
        college="计算机学院",
        major="软件工程",
        role=role,
        is_staff=role == User.Role.ADMIN,
    )


def seed_contact(user: User, *, qq: str = "", wechat: str = "", phone: str = "") -> ContactInfo:
    """User 创建时会自动建空 ContactInfo 行（profiles.signals），这里只回填值。"""

    contact, _ = ContactInfo.objects.update_or_create(
        user=user,
        defaults={"qq": qq or None, "wechat": wechat or None, "phone": phone or None},
    )
    return contact


def make_staff(*, uid: str = "0000000901", email: str = "room-ops@cohabit.local"):
    staff = make_user(uid=uid, email=email, nickname="寝室运营", role=User.Role.ADMIN)
    staff.is_staff = True
    staff.is_superuser = True
    staff.save(update_fields=["is_staff", "is_superuser"])
    return staff


def make_admin_request(user, *, request_id: str = "room-ops"):
    request = RequestFactory().post("/admin/rooms/room/", HTTP_X_REQUEST_ID=request_id)
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def make_bare_room(owner: User, *, status: str = Room.Status.DISSOLVED) -> Room:
    """不经过 ``make_room``，因此没有任何成员行（用于删除保护的正例）。"""

    return Room.objects.create(
        code=next_room_code(),
        title="空寝室",
        owner=owner,
        capacity=4,
        member_count=0,
        gender="MALE",
        college="计算机学院",
        major="软件工程",
        tags=[],
        status=status,
    )


def parse_csv(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def room_with_members():
    staff = make_staff()
    owner = make_user(uid="0000000902", email="owner902@stu.edu.cn", nickname="房主902")
    member = make_user(uid="0000000903", email="member903@stu.edu.cn", nickname="成员903")
    room = Room.objects.create(
        code=next_room_code(),
        title="测试寝室",
        owner=owner,
        capacity=4,
        member_count=2,
        gender="MALE",
        college="计算机学院",
        major="软件工程",
        tags=[],
    )
    RoomMember.objects.create(room=room, user=owner, role=RoomMember.Role.OWNER)
    RoomMember.objects.create(room=room, user=member, role=RoomMember.Role.MEMBER)
    return staff, owner, member, room


def test_room_admin_registers_actions_filters_and_export():
    model_admin = RoomAdmin(Room, AdminSite())

    assert {"force_dissolve_rooms", "export_rooms_csv"} <= set(model_admin.actions)
    assert ("created_at", django_admin.DateFieldListFilter) in model_admin.list_filter
    assert "status" in model_admin.list_filter
    staff = make_staff(uid="0000000908", email="ops908@cohabit.local")
    assert model_admin.has_add_permission(make_admin_request(staff)) is True
    assert MUST_DISSOLVE_BEFORE_DELETE == "MUST_DISSOLVE_BEFORE_DELETE"


def test_force_dissolve_closes_room_and_bypasses_window():
    staff, owner, member, room = room_with_members()
    connection = ConnectionRequest.objects.create(
        type=ConnectionRequest.Type.INVITE,
        initiator=owner,
        target=member,
        room=room,
        status=ConnectionRequest.Status.PENDING,
        expires_at=timezone.now() + timedelta(hours=12),
    )
    # 窗口关闭后学生端无法解散，但 Admin 的 force 分支必须仍可操作。
    window = open_window("计算机学院")
    window.end_at = timezone.now() - timedelta(minutes=1)
    window.save(update_fields=["end_at", "updated_at"])
    model_admin = RoomAdmin(Room, AdminSite())
    request = make_admin_request(staff)

    model_admin.force_dissolve_rooms(request, Room.objects.filter(pk=room.pk))

    room.refresh_from_db()
    assert room.status == Room.Status.DISSOLVED
    assert room.member_count == 0
    assert room.dissolved_at is not None
    assert not room.members.filter(status=RoomMember.Status.ACTIVE).exists()
    assert set(room.members.values_list("status", flat=True)) == {RoomMember.Status.LEFT}
    assert set(room.members.values_list("reason", flat=True)) == {RoomMember.Reason.DISSOLVED}
    connection.refresh_from_db()
    assert connection.status == ConnectionRequest.Status.CANCELLED
    assert connection.close_reason == ConnectionRequest.CloseReason.ROOM_DISSOLVED
    audit = AuditLog.objects.get(action="ROOM_FORCE_DISSOLVED", target_id=room.pk)
    assert audit.actor_id == staff.pk
    assert audit.target_type == AuditLog.TargetType.ROOM
    assert audit.meta == {"member_count": 2}
    assert audit.request_id == "room-ops"
    assert (
        Notification.objects.filter(type=Notification.Type.ROOM_DISSOLVED).count() == 2
    )
    notes = [str(message) for message in get_messages(request)]
    assert any("ROOM_FORCE_DISSOLVED" in note or "解散" in note for note in notes)


def test_force_dissolve_reports_error_without_crashing():
    staff = make_staff(uid="0000000904", email="ops904@cohabit.local")
    owner = make_user(uid="0000000905", email="owner905@stu.edu.cn", nickname="房主905")
    room = make_bare_room(owner, status=Room.Status.DISSOLVED)
    model_admin = RoomAdmin(Room, AdminSite())
    request = make_admin_request(staff)

    model_admin.force_dissolve_rooms(request, Room.objects.filter(pk=room.pk))

    notes = [str(message) for message in get_messages(request)]
    assert notes  # 失败逐条给出错误提示，而不是抛异常中断整批
    room.refresh_from_db()
    assert room.status == Room.Status.DISSOLVED


def test_room_with_active_members_cannot_be_deleted():
    staff, owner, member, room = room_with_members()
    model_admin = RoomAdmin(Room, AdminSite())
    request = make_admin_request(staff)

    # 只返回 False，不写 message（Admin 渲染 change 页也会调用本方法）。
    assert model_admin.has_delete_permission(request, room) is False
    assert not [
        str(message) for message in get_messages(request)
    ], "has_delete_permission 不应产生任何 message"

    # 真正执行删除时才给出「请先解散」提示，并且不落库。
    model_admin.delete_model(request, room)
    assert Room.objects.filter(pk=room.pk).exists()
    notes = [str(message) for message in get_messages(request)]
    assert any(
        MUST_DISSOLVE_BEFORE_DELETE in note and "先解散" in note for note in notes
    )

    model_admin.delete_queryset(request, Room.objects.filter(pk=room.pk))
    assert Room.objects.filter(pk=room.pk).exists()
    assert room.members.count() == 2


def test_room_change_page_does_not_warn_about_dissolve():
    """打开有成员的寝室详情页不应弹出「请先解散」错误（R-21 提示只在删除时给）。"""

    staff, owner, member, room = room_with_members()
    client = Client()
    client.force_login(staff)

    response = client.get(f"/admin/rooms/room/{room.pk}/change/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "请先解散" not in content
    assert MUST_DISSOLVE_BEFORE_DELETE not in content
    # 详情页仍可用，寝室未被改动。
    room.refresh_from_db()
    assert room.status == Room.Status.RECRUITING
    assert room.member_count == 2


def test_session_owner_and_member_deleted_together_with_room():
    staff, owner, member, room = room_with_members()
    empty = make_bare_room(owner)
    model_admin = RoomAdmin(Room, AdminSite())
    request = make_admin_request(staff)

    model_admin.delete_queryset(request, Room.objects.filter(pk__in=[room.pk, empty.pk]))

    assert Room.objects.filter(pk=room.pk).exists()  # 有成员 → 保留
    assert not Room.objects.filter(pk=empty.pk).exists()  # 无成员 → 删除


def test_room_without_active_members_can_be_deleted():
    staff = make_staff(uid="0000000906", email="ops906@cohabit.local")
    owner = make_user(uid="0000000907", email="owner907@stu.edu.cn", nickname="房主907")
    room = make_bare_room(owner)
    model_admin = RoomAdmin(Room, AdminSite())
    request = make_admin_request(staff)

    assert model_admin.has_delete_permission(request, room) is True
    model_admin.delete_queryset(request, Room.objects.filter(pk=room.pk))

    assert not Room.objects.filter(pk=room.pk).exists()


def test_export_rooms_csv_whitelist_and_audit():
    staff, owner, member, room = room_with_members()
    seed_contact(owner, qq=QQ, wechat=WECHAT, phone=PHONE)
    model_admin = RoomAdmin(Room, AdminSite())

    response = model_admin.export_rooms_csv(
        make_admin_request(staff, request_id="room-export"),
        Room.objects.filter(pk=room.pk),
    )

    rows = parse_csv(response)
    assert tuple(rows[0]) == ROOM_EXPORT_COLUMNS
    body = response.content.decode("utf-8-sig")
    assert QQ not in body and WECHAT not in body and PHONE not in body
    assert not any(token in body.lower() for token in FORBIDDEN_TOKENS)
    assert "房主902" not in body  # 只导出 uid，不含昵称/联系方式
    audit = AuditLog.objects.get(action="AUDIT_EXPORTED", request_id="room-export")
    assert audit.actor_id == staff.pk
    assert audit.meta == {
        "model": "Room",
        "count": 1,
        "columns": list(ROOM_EXPORT_COLUMNS),
    }


def test_export_room_members_csv_whitelist_and_audit():
    staff, owner, member, room = room_with_members()
    seed_contact(member, qq=QQ, wechat=WECHAT, phone=PHONE)
    model_admin = RoomMemberAdmin(RoomMember, AdminSite())

    response = model_admin.export_room_members_csv(
        make_admin_request(staff, request_id="member-export"),
        RoomMember.objects.filter(room=room),
    )

    rows = parse_csv(response)
    assert tuple(rows[0]) == ROOM_MEMBER_EXPORT_COLUMNS
    body = response.content.decode("utf-8-sig")
    assert QQ not in body and WECHAT not in body and PHONE not in body
    assert not any(token in body.lower() for token in FORBIDDEN_TOKENS)
    assert "export_room_members_csv" in model_admin.actions
    audit = AuditLog.objects.get(action="AUDIT_EXPORTED", request_id="member-export")
    assert audit.meta["count"] == 2


def test_member_and_transfer_admins_have_date_filters():
    member_admin = RoomMemberAdmin(RoomMember, AdminSite())
    transfer_admin = RoomTransferAdmin(RoomTransfer, AdminSite())

    assert ("created_at", django_admin.DateFieldListFilter) in member_admin.list_filter
    assert "export_room_members_csv" in member_admin.actions
    assert ("created_at", django_admin.DateFieldListFilter) in transfer_admin.list_filter
    assert "export_room_transfers_csv" not in transfer_admin.actions
