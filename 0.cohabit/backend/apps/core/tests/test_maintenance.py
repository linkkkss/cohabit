"""定时维护命令测试（docs/06 M5 W-05…W-10、T-08、R-15…R-17、S-15）。"""

from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.adminops import maintenance
from apps.adminops.models import AuditLog, TimeWindow
from apps.connections.models import OPEN_STATUSES, ConnectionRequest
from apps.connections.tests.helpers import complete_profile
from apps.notifications.models import Notification
from apps.rooms.models import Room, RoomMember, RoomTransfer
from apps.rooms.services import archive_room, dissolve_room
from apps.rooms.tests.helpers import (
    add_member,
    auth_client,
    body,
    error_code,
    make_connection,
    make_room,
    make_user,
    open_window,
)
from apps.rooms.utils import isoformat

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def run(name: str, *args: str) -> str:
    """调用管理命令并返回标准输出。"""
    out = StringIO()
    call_command(name, *args, stdout=out)
    return out.getvalue()


def make_notification(
    user,
    *,
    type: str = Notification.Type.SYSTEM,
    payload: dict[str, Any] | None = None,
    created_at=None,
    read_at=None,
) -> Notification:
    row = Notification.objects.create(
        user=user,
        type=type,
        title="占位标题",
        payload=payload or {},
    )
    fields: dict[str, Any] = {}
    if created_at is not None:
        fields["created_at"] = created_at
    if read_at is not None:
        fields["read_at"] = read_at
    if fields:
        Notification.objects.filter(pk=row.pk).update(**fields)
    row.refresh_from_db()
    return row


def make_audit() -> AuditLog:
    return AuditLog.objects.create(
        action="TEST_ACTION",
        target_type=AuditLog.TargetType.USER,
        target_id=1,
    )


@pytest.fixture
def owner():
    return make_user(uid="1000001001", email="owner@example.com", nickname="小满")


@pytest.fixture
def member():
    return make_user(uid="1000001002", email="member@example.com", nickname="小林")


@pytest.fixture
def stranger():
    return make_user(uid="1000001003", email="stranger@example.com", nickname="阿泽")


# --------------------------------------------------------------------------- #
# 1. expire_connections（docs/02 §3.6、W-06）
# --------------------------------------------------------------------------- #
def test_expire_connections_closes_due_request(owner, member):
    open_window()
    row = make_connection(initiator=owner, target=member, expires_in=timedelta(minutes=-5))
    version_before = row.version

    out = run("expire_connections")

    row.refresh_from_db()
    assert "expire_connections:" in out
    assert "closed=1" in out
    assert row.status == ConnectionRequest.Status.EXPIRED
    assert row.close_reason == ConnectionRequest.CloseReason.TIMEOUT
    assert row.closed_by_id is None
    assert row.version == version_before + 1
    notifications = Notification.objects.filter(type=Notification.Type.SYSTEM)
    assert notifications.count() == 2
    assert {item.user_id for item in notifications} == {owner.pk, member.pk}
    assert notifications.first().payload["reason"] == "TIMEOUT"
    audit = AuditLog.objects.get(action="CONNECTION_EXPIRED")
    assert audit.target_type == AuditLog.TargetType.CONNECTION
    assert audit.target_id == row.pk
    assert audit.meta["reason"] == "TIMEOUT"
    assert audit.actor_id is None


def test_expire_connections_is_idempotent(owner, member):
    open_window()
    make_connection(initiator=owner, target=member, expires_in=timedelta(minutes=-5))

    first = run("expire_connections")
    second = run("expire_connections")

    assert "closed=1" in first
    assert "closed=0" in second
    assert Notification.objects.count() == 2
    assert AuditLog.objects.filter(action="CONNECTION_EXPIRED").count() == 1


def test_expire_connections_dry_run_writes_nothing(owner, member):
    open_window()
    row = make_connection(initiator=owner, target=member, expires_in=timedelta(minutes=-5))

    out = run("expire_connections", "--dry-run")

    row.refresh_from_db()
    assert "due=1" in out
    assert "closed=0" in out
    assert row.status == ConnectionRequest.Status.PENDING
    assert Notification.objects.count() == 0
    assert AuditLog.objects.filter(action="CONNECTION_EXPIRED").count() == 0


def test_expire_connections_keeps_future_requests(owner, member):
    open_window()
    row = make_connection(initiator=owner, target=member, expires_in=timedelta(hours=1))

    out = run("expire_connections")

    row.refresh_from_db()
    assert "closed=0" in out
    assert row.status == ConnectionRequest.Status.PENDING


# --------------------------------------------------------------------------- #
# 2. archive_rooms（docs/02 §7.4、W-05/W-06/W-09/W-10、R-15…R-17、T-08）
# --------------------------------------------------------------------------- #
def _ended_window():
    return open_window(ends_in=timedelta(minutes=-5))


def test_archive_rooms_expires_open_requests_then_archives(owner, member):
    window = _ended_window()
    room = make_room(owner, members=(member,))
    # 未到期的在途请求：窗口结束时也要被强制过期（不等 48h/7d）。
    pending = make_connection(initiator=owner, target=member, expires_in=timedelta(hours=10))

    out = run("archive_rooms")

    pending.refresh_from_db()
    room.refresh_from_db()
    assert "expired=1" in out
    assert "archived=1" in out
    assert pending.status == ConnectionRequest.Status.EXPIRED
    assert pending.close_reason == ConnectionRequest.CloseReason.TIMEOUT
    assert room.status == Room.Status.ARCHIVED
    assert room.archived_at is not None
    assert not ConnectionRequest.objects.filter(status__in=OPEN_STATUSES).exists()
    assert AuditLog.objects.filter(action="CONNECTION_EXPIRED").count() == 1
    audit = AuditLog.objects.get(action="ROOM_ARCHIVED")
    assert audit.target_id == room.pk
    assert audit.meta["window_end"] == isoformat(window.end_at)
    assert Notification.objects.filter(type=Notification.Type.ROOM_ARCHIVED).count() == 2


def test_archive_rooms_marks_members_archived_and_frees_slot(owner, member, stranger):
    _ended_window()
    room = make_room(owner, members=(member,))

    run("archive_rooms")

    rows = RoomMember.objects.filter(room_id=room.pk)
    assert {row.status for row in rows} == {RoomMember.Status.ARCHIVED}
    assert {row.reason for row in rows} == {RoomMember.Reason.ARCHIVED}
    # R-16：归档成员不再占用“一人一寝”，可以加入新寝室。
    other = make_room(stranger)
    add_member(other, member)
    assert RoomMember.objects.filter(
        user=member, status=RoomMember.Status.ACTIVE
    ).count() == 1


def test_archive_rooms_is_idempotent(owner, member):
    _ended_window()
    make_room(owner, members=(member,))

    first = run("archive_rooms")
    second = run("archive_rooms")

    assert "archived=1" in first
    assert "expired=0" in second
    assert "archived=0" in second
    assert "remaining_rooms=0" in second
    assert AuditLog.objects.filter(action="ROOM_ARCHIVED").count() == 1


def test_archive_rooms_dry_run_writes_nothing(owner, member):
    _ended_window()
    room = make_room(owner, members=(member,))
    make_connection(initiator=owner, target=member, expires_in=timedelta(hours=10))

    out = run("archive_rooms", "--dry-run")

    room.refresh_from_db()
    assert "rooms=1" in out
    assert "archived=0" in out
    assert room.status == Room.Status.RECRUITING
    assert ConnectionRequest.objects.filter(status=ConnectionRequest.Status.PENDING).count() == 1
    assert AuditLog.objects.filter(action="ROOM_ARCHIVED").count() == 0


def test_archive_rooms_skips_dissolved_room(owner, member):
    window = open_window()
    room = make_room(owner, members=(member,))
    # 解散必须在窗口内完成，之后把窗口挪到过去模拟“窗口已结束”。
    dissolve_room(owner, room.pk)
    TimeWindow.objects.filter(pk=window.pk).update(
        start_at=timezone.now() - timedelta(hours=2),
        end_at=timezone.now() - timedelta(minutes=5),
    )

    out = run("archive_rooms")

    room.refresh_from_db()
    assert "archived=0" in out
    assert room.status == Room.Status.DISSOLVED


def test_archive_rooms_does_not_archive_when_window_extended(owner, member):
    # W-10：窗口延长回未来后不应再归档。
    open_window(ends_in=timedelta(hours=2))
    room = make_room(owner, members=(member,))

    out = run("archive_rooms")

    room.refresh_from_db()
    assert "windows=0" in out
    assert room.status == Room.Status.RECRUITING


def test_archive_rooms_cancels_pending_transfer(owner, member):
    _ended_window()
    room = make_room(owner, members=(member,))
    transfer = RoomTransfer.objects.create(
        room=room,
        from_owner=owner,
        to_member=member,
        status=RoomTransfer.Status.PENDING,
        expires_at=timezone.now() + timedelta(hours=24),
    )

    run("archive_rooms")

    transfer.refresh_from_db()
    assert transfer.status == RoomTransfer.Status.CANCELLED
    assert Notification.objects.filter(type=Notification.Type.TRANSFER_CANCELLED).count() == 2


def test_archive_rooms_public_page_404_and_member_read_only(owner, member, stranger):
    _ended_window()
    room = make_room(owner, members=(member,))

    run("archive_rooms")

    public = auth_client(stranger).get(f"/api/rooms/{room.code}")
    mine = body(auth_client(member).get("/api/rooms/mine"))
    assert public.status_code == 404
    assert error_code(public) == "ROOM_NOT_FOUND"
    assert mine["room"]["status"] == Room.Status.ARCHIVED
    assert all(value is False for value in mine["room"]["actions"].values())


def test_confirm_after_archive_cannot_join_room(owner, member):
    """W-08 的确定性版本：归档后请求已关闭且窗口结束，确认不可能入寝。"""
    _ended_window()
    room = make_room(owner, members=(member,))
    pending = make_connection(
        initiator=owner,
        target=member,
        status=ConnectionRequest.Status.CONFIRMING,
        expires_in=timedelta(hours=10),
    )
    before_members = RoomMember.objects.filter(room_id=room.pk).count()
    before_count = room.member_count

    run("archive_rooms")

    pending.refresh_from_db()
    room.refresh_from_db()
    # docs/02 §7.4 第 2 步先强制过期该学院在途请求（EXPIRED/TIMEOUT），
    # 第 3 步归档时已无残留请求，因此这里断言的是过期路径。
    assert pending.status == ConnectionRequest.Status.EXPIRED
    assert pending.close_reason == ConnectionRequest.CloseReason.TIMEOUT
    from apps.accounts.exceptions import ApiError
    from apps.connections import services as connection_services

    with pytest.raises(ApiError) as excinfo:
        connection_services.confirm_request(owner, pending.pk)
    assert excinfo.value.status_code == 409
    assert excinfo.value.error_code in {"REQUEST_CLOSED", "WINDOW_CLOSED"}
    assert RoomMember.objects.filter(room_id=room.pk).count() == before_members
    assert room.member_count == before_count


# --------------------------------------------------------------------------- #
# 3. send_window_reminders（docs/02 §7.5、W-07）
# --------------------------------------------------------------------------- #
def test_send_window_reminders_sends_7_3_1_once(owner, member):
    window = open_window(ends_in=timedelta(days=7))
    make_room(owner, members=(member,))
    base = window.end_at - timedelta(days=7)

    seven = maintenance.send_window_reminders(now=base)
    three = maintenance.send_window_reminders(now=base + timedelta(days=4))
    one = maintenance.send_window_reminders(now=base + timedelta(days=6))
    repeat = maintenance.send_window_reminders(now=base)

    assert seven["sent"] == 2  # owner + member
    assert three["sent"] == 2
    assert one["sent"] == 2
    assert repeat["sent"] == 0
    assert repeat["skipped"] == 2
    rows = Notification.objects.filter(type=Notification.Type.WINDOW_CLOSING)
    assert rows.count() == 6
    assert {row.user_id for row in rows} == {owner.pk, member.pk}
    assert {json.dumps(row.payload, sort_keys=True) for row in rows} == {
        json.dumps(
            {
                "college": window.college,
                "end_at": isoformat(window.end_at),
                "days_left": days,
            },
            sort_keys=True,
        )
        for days in (7, 3, 1)
    }
    titles = {row.title for row in rows}
    assert titles == {"组寝窗口还有 7 天关闭", "组寝窗口还有 3 天关闭", "组寝窗口还有 1 天关闭"}


def test_send_window_reminders_skips_non_reminder_day(owner, member):
    open_window(ends_in=timedelta(days=5))
    make_room(owner, members=(member,))

    out = run("send_window_reminders")

    assert "sent=0" in out
    assert Notification.objects.filter(type=Notification.Type.WINDOW_CLOSING).count() == 0


def test_send_window_reminders_includes_open_request_parties(owner, member):
    open_window(ends_in=timedelta(days=7))
    make_connection(initiator=owner, target=member, expires_in=timedelta(hours=10))

    out = run("send_window_reminders")

    assert "sent=2" in out
    rows = Notification.objects.filter(type=Notification.Type.WINDOW_CLOSING)
    assert {row.user_id for row in rows} == {owner.pk, member.pk}


def test_send_window_reminders_excludes_unrelated_and_disabled(owner, stranger, member):
    open_window(ends_in=timedelta(days=7))
    make_room(owner)
    member.status = "DISABLED"
    member.save(update_fields=["status"])
    make_room(member)

    out = run("send_window_reminders")

    assert "sent=1" in out
    rows = Notification.objects.filter(type=Notification.Type.WINDOW_CLOSING)
    assert {row.user_id for row in rows} == {owner.pk}


def test_send_window_reminders_dry_run(owner):
    open_window(ends_in=timedelta(days=7))
    make_room(owner)

    out = run("send_window_reminders", "--dry-run")

    assert "due=1" in out
    assert "sent=0" in out
    assert Notification.objects.filter(type=Notification.Type.WINDOW_CLOSING).count() == 0


def test_send_window_reminders_no_window(owner):
    out = run("send_window_reminders")
    assert "windows=0" in out
    assert "sent=0" in out


# --------------------------------------------------------------------------- #
# 4. cleanup_notifications（docs/02 §8.1）
# --------------------------------------------------------------------------- #
def test_cleanup_notifications_removes_old_and_keeps_recent(owner):
    now = timezone.now()
    audit = make_audit()
    old_read = make_notification(
        owner,
        created_at=now - timedelta(days=200),
        read_at=now - timedelta(days=91),
    )
    old_unread = make_notification(owner, created_at=now - timedelta(days=181))
    recent_unread = make_notification(owner, created_at=now - timedelta(days=179))
    recent_read = make_notification(
        owner,
        created_at=now - timedelta(days=100),
        read_at=now - timedelta(days=89),
    )

    out = run("cleanup_notifications")

    assert "read_deleted=1" in out
    assert "unread_deleted=1" in out
    remaining = set(Notification.objects.values_list("pk", flat=True))
    assert remaining == {recent_unread.pk, recent_read.pk}
    assert not Notification.objects.filter(pk=old_read.pk).exists()
    assert not Notification.objects.filter(pk=old_unread.pk).exists()
    # 审计不受影响（D-20）。
    assert AuditLog.objects.filter(pk=audit.pk).exists()


def test_cleanup_notifications_dry_run(owner):
    now = timezone.now()
    make_notification(
        owner,
        created_at=now - timedelta(days=200),
        read_at=now - timedelta(days=91),
    )

    out = run("cleanup_notifications", "--dry-run")

    assert "read_due=1" in out
    assert "read_deleted=0" in out
    assert Notification.objects.count() == 1


# --------------------------------------------------------------------------- #
# 5. expire_transfers（docs/02 §6、T-07）
# --------------------------------------------------------------------------- #
def test_expire_transfers_closes_due_and_is_idempotent(owner, member):
    open_window()
    room = make_room(owner, members=(member,))
    transfer = RoomTransfer.objects.create(
        room=room,
        from_owner=owner,
        to_member=member,
        status=RoomTransfer.Status.PENDING,
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    first = run("expire_transfers")
    second = run("expire_transfers")

    transfer.refresh_from_db()
    assert "expired=1" in first
    assert "expired=0" in second
    assert transfer.status == RoomTransfer.Status.EXPIRED
    assert transfer.decided_at is not None
    assert Notification.objects.filter(type=Notification.Type.TRANSFER_EXPIRED).count() == 2
    assert AuditLog.objects.filter(action="TRANSFER_EXPIRED").count() == 1


def test_expire_transfers_dry_run(owner, member):
    open_window()
    room = make_room(owner, members=(member,))
    transfer = RoomTransfer.objects.create(
        room=room,
        from_owner=owner,
        to_member=member,
        status=RoomTransfer.Status.PENDING,
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    out = run("expire_transfers", "--dry-run")

    transfer.refresh_from_db()
    assert "due=1" in out
    assert transfer.status == RoomTransfer.Status.PENDING


# --------------------------------------------------------------------------- #
# 6. repair_member_count（docs/06 S-15）
# --------------------------------------------------------------------------- #
def test_repair_member_count_dry_run_detects_drift(owner, member):
    room = make_room(owner, members=(member,), member_count=4)

    out = run("repair_member_count", "--dry-run")

    room.refresh_from_db()
    assert "drift=1" in out
    assert f"{room.pk}:4->2" in out
    assert room.member_count == 4


def test_repair_member_count_fixes_drift(owner, member):
    room = make_room(owner, members=(member,), member_count=4)

    out = run("repair_member_count")

    room.refresh_from_db()
    assert "repaired=" in out
    assert room.member_count == 2
    audit = AuditLog.objects.get(action="ROOM_MEMBER_COUNT_REPAIRED")
    assert audit.meta["before"] == 4
    assert audit.meta["after"] == 2

    again = run("repair_member_count")
    assert "repaired=0" in again


def test_repair_member_count_skips_archived_snapshot(owner, member):
    room = make_room(owner, members=(member,))
    archive_room(room.pk)
    room.refresh_from_db()
    snapshot = room.member_count

    out = run("repair_member_count", "--dry-run")

    assert "drift=0" in out
    run("repair_member_count")
    room.refresh_from_db()
    assert room.status == Room.Status.ARCHIVED
    assert room.member_count == snapshot


def test_repair_member_count_room_option(owner, member, stranger):
    drifted = make_room(owner, members=(member,), member_count=4)
    other = make_room(stranger, member_count=3)

    run("repair_member_count", "--room", str(drifted.pk))

    drifted.refresh_from_db()
    other.refresh_from_db()
    assert drifted.member_count == 2
    assert other.member_count == 3


# --------------------------------------------------------------------------- #
# 命令出口约定（cron 日志：name + 计数）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name",
    [
        "expire_connections",
        "archive_rooms",
        "send_window_reminders",
        "cleanup_notifications",
        "expire_transfers",
        "repair_member_count",
    ],
)
def test_commands_emit_named_counters(name):
    out = run(name, "--dry-run")
    assert out.startswith(f"{name}: ")
    assert "dry_run=True" in out


# --------------------------------------------------------------------------- #
# 窗口规则回归（W-01/W-02/W-04）：维护任务不得改变窗口语义
# --------------------------------------------------------------------------- #
def _invite(client, target):
    payload = {"type": "INVITE", "target_uid": target.uid, "capacity_pref": 4}
    return client.post("/api/connections", payload, format="json")


@pytest.mark.parametrize("state", ["missing", "unstarted", "ended"])
def test_window_write_guard_and_reads(owner, member, state):
    """W-01/W-02：无窗口/未开始/已结束 → 写 409，读仍 200。"""
    if state == "unstarted":
        open_window(starts_in=timedelta(hours=1), ends_in=timedelta(hours=2))
    elif state == "ended":
        open_window(ends_in=timedelta(minutes=-5))
    complete_profile(owner)
    complete_profile(member)

    response = _invite(auth_client(owner), member)

    assert response.status_code == 409
    assert error_code(response) == "WINDOW_CLOSED"
    assert auth_client(owner).get("/api/rooms").status_code == 200


def test_window_closed_still_allows_reports_and_notification_reads(owner, member):
    """W-04：窗口关闭后举报与通知已读仍然可用。"""
    open_window(ends_in=timedelta(minutes=-5))

    report = auth_client(owner).post(
        "/api/reports",
        {"target_type": "USER", "target_id": member.pk, "reason": "窗口关闭时举报"},
        format="json",
    )
    listed = auth_client(owner).get("/api/notifications")

    assert report.status_code == 201
    assert listed.status_code == 200
