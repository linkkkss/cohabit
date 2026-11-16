"""``seed_demo`` 演示数据生成命令测试（docs/seed-spec.md）。"""

from __future__ import annotations

import io

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ContactInfo, InviteCode, User
from apps.adminops.models import AuditLog, Block, Report, TimeWindow
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.profiles.constants import DIMENSIONS, QUESTIONNAIRE_VERSION
from apps.profiles.dims import compute_dims
from apps.profiles.models import Profile
from apps.rooms.models import Room, RoomMember, RoomTransfer

pytestmark = pytest.mark.django_db

ROOM_CODES = {f"10000000{index}" for index in range(1, 7)}
COLLEGES = {"计算机学院", "外国语学院"}
STUDENT_PASSWORD = "Demo1234!"
ADMIN_EMAIL = "admin@cohabit.local"
FORBIDDEN_PAYLOAD_KEYS = {"qq", "wechat", "phone", "email", "contact", "token"}


def run_seed(*args: str) -> str:
    # 测试环境 settings.DEBUG 恒为 False，按 docs/seed-spec §1.3 需显式 --force。
    out = io.StringIO()
    base = ["--force"] if "--force" not in args else []
    call_command("seed_demo", *base, *args, stdout=out)
    return out.getvalue()


def test_seed_demo_creates_demo_dataset():
    output = run_seed("--reset")

    assert "seed_demo: ok" in output
    assert User.objects.filter(role=User.Role.STUDENT).count() == 40
    assert User.objects.filter(role=User.Role.ADMIN).count() == 1
    assert User.objects.filter(email=ADMIN_EMAIL).exists()

    # 画像：全部 100 分，且 dims 与服务端纯函数一致。
    profiles = Profile.objects.select_related("user")
    assert profiles.count() == 40
    for profile in profiles:
        assert profile.completeness == 100
        assert profile.questionnaire_version == QUESTIONNAIRE_VERSION
        assert set(profile.dims) == set(DIMENSIONS)
        assert profile.dims == compute_dims(profile.hard_answers, profile.soft_answers)
        assert len(profile.hard_answers) == 11
        assert len(profile.soft_answers) == 6
        assert 3 <= len(profile.tags) <= 8
        assert 2 <= len(profile.prompts) <= 3
        assert profile.red_lines_confirmed is True

    assert ContactInfo.objects.count() == 40
    assert ContactInfo.objects.filter(qq__isnull=False).count() == 4

    # 寝室的容量 / 状态 / 成员数矩阵。
    rooms = {room.code: room for room in Room.objects.select_related("owner")}
    assert set(rooms) == ROOM_CODES
    assert {room.capacity for room in rooms.values()} == {2, 4, 6}
    statuses = [rooms[code].status for code in sorted(ROOM_CODES)]
    assert statuses == [
        Room.Status.RECRUITING,
        Room.Status.RECRUITING,
        Room.Status.FULL,
        Room.Status.LOCKED,
        Room.Status.ARCHIVED,
        Room.Status.DISSOLVED,
    ]
    assert [rooms[code].member_count for code in sorted(ROOM_CODES)] == [
        2,
        3,
        4,
        3,
        6,
        0,
    ]
    assert rooms["100000005"].archived_at is not None
    assert rooms["100000006"].dissolved_at is not None

    members = RoomMember.objects.all()
    assert members.count() == 20
    assert members.filter(status=RoomMember.Status.ARCHIVED).count() == 6
    assert members.filter(status=RoomMember.Status.LEFT).count() == 2
    for room in rooms.values():
        # ARCHIVED 保留归档时快照，DISSOLVED 归零，都不按 ACTIVE 计数校验。
        if room.status in {Room.Status.ARCHIVED, Room.Status.DISSOLVED}:
            continue
        active = members.filter(room=room, status=RoomMember.Status.ACTIVE)
        assert room.member_count == active.count()
        assert active.filter(role=RoomMember.Role.OWNER).count() == 1

    # 请求 / 转让 / 举报 / 拉黑 / 审计 / 窗口 / 邀请码。
    assert ConnectionRequest.objects.count() == 8
    confirmed = ConnectionRequest.objects.filter(
        status=ConnectionRequest.Status.CONFIRMED
    )
    assert confirmed.count() == 2
    assert list(confirmed.values_list("expires_at", flat=True)) == [None, None]
    open_states = ConnectionRequest.objects.exclude(
        status=ConnectionRequest.Status.CONFIRMED
    )
    assert open_states.count() == 6
    assert not open_states.filter(expires_at__isnull=True).exists()
    assert RoomTransfer.objects.count() == 2
    assert Report.objects.count() == 2
    assert Block.objects.count() == 4
    assert AuditLog.objects.count() == 10
    assert TimeWindow.objects.count() == 2
    assert set(TimeWindow.objects.values_list("college", flat=True)) == COLLEGES
    for window in TimeWindow.objects.all():
        assert window.start_at <= timezone.now() < window.end_at
    invite = InviteCode.objects.get(code="COHAB2026")
    assert invite.is_active is True
    assert invite.is_usable() is True

    # 通知：类型覆盖、每人上限、载荷不含联系方式。
    notes = Notification.objects.all()
    assert 70 <= notes.count() <= 90
    assert len(set(notes.values_list("type", flat=True))) >= 10
    per_user = {}
    for note in notes:
        per_user[note.user_id] = per_user.get(note.user_id, 0) + 1
        assert not (FORBIDDEN_PAYLOAD_KEYS & set(note.payload))
        assert len(note.title) <= 60
    assert max(per_user.values()) <= 5

    # 演示账号可登录。
    client = APIClient()
    response = client.post(
        "/api/auth/login/",
        {"email": "demo001@stu.edu.cn", "password": STUDENT_PASSWORD},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["user"]["nickname"] == "小算01"


def test_seed_demo_is_repeatable_and_guarded():
    run_seed("--reset")
    first = (
        User.objects.count(),
        Room.objects.count(),
        RoomMember.objects.count(),
        ConnectionRequest.objects.count(),
        Notification.objects.count(),
        AuditLog.objects.count(),
    )

    run_seed("--reset")
    second = (
        User.objects.count(),
        Room.objects.count(),
        RoomMember.objects.count(),
        ConnectionRequest.objects.count(),
        Notification.objects.count(),
        AuditLog.objects.count(),
    )
    assert first == second

    with pytest.raises(CommandError) as excinfo:
        call_command("seed_demo", "--force", stdout=io.StringIO())
    assert excinfo.value.returncode == 2
    assert "已存在种子数据" in str(excinfo.value)


def test_seed_demo_rejects_non_debug_without_force(settings):
    settings.DEBUG = False
    assert settings.DEBUG is False

    with pytest.raises(CommandError) as excinfo:
        call_command("seed_demo", stdout=io.StringIO())
    assert "--force" in str(excinfo.value)


def test_seed_demo_rejects_production_environment(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setenv("ENV", "production")

    with pytest.raises(CommandError) as excinfo:
        call_command("seed_demo", "--force", stdout=io.StringIO())
    assert "生产环境" in str(excinfo.value)


def test_seed_demo_reset_keeps_extra_admin():
    """P3-2：手工创建的额外 ADMIN 允许存在，--reset 不因 I-01 失败且不删除它。"""
    extra = User.objects.create_superuser(
        email="ops-admin@cohabit.local",
        password="OpsAdmin1234!",
        uid="0000000098",
        nickname="额外管理员",
        gender=User.Gender.MALE,
        college="计算机学院",
    )
    assert extra.role == User.Role.ADMIN

    output = run_seed("--reset")

    assert "seed_demo: ok" in output
    extra.refresh_from_db()
    assert extra.role == User.Role.ADMIN
    assert User.objects.filter(pk=extra.pk).exists()
    # 种子管理员依然存在且唯一；全库 ADMIN 数允许 >1。
    assert (
        User.objects.filter(
            uid="0000000099", email=ADMIN_EMAIL, role=User.Role.ADMIN
        ).count()
        == 1
    )
    assert User.objects.filter(role=User.Role.ADMIN).count() == 2


def RoomTransfer_count() -> int:
    from apps.rooms.models import RoomTransfer

    return RoomTransfer.objects.count()
