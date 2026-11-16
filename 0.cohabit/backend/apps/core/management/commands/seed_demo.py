"""``seed_demo``：按 docs/seed-spec.md 生成 M1 演示种子数据。

命令契约（docs/seed-spec.md §1）：

* ``python manage.py seed_demo``：空库时创建；
* ``python manage.py seed_demo --reset``：先删除本命令创建的种子对象再重建；
* ``python manage.py seed_demo --force``：仅在 ``DEBUG=False`` 时需要；
* ``--dry-run``：完整跑一遍后回滚，只打印计数。

全部写入在**单个事务**内完成；提交前执行 docs/seed-spec.md §10 的断言，
任一失败即回滚（退出码 1）。命令只触碰种子对象，非种子数据原样保留。
"""

from __future__ import annotations

import os
import time as timer
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.accounts.models import ContactInfo, InviteCode, User
from apps.adminops.models import AuditLog, Block, Report, TimeWindow
from apps.connections.models import ConnectionRequest
from apps.core.audit import write_audit
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.profiles.constants import PROMPT_ORDER, QUESTIONNAIRE_VERSION
from apps.profiles.dims import compute_dims
from apps.profiles.models import Profile
from apps.profiles.services import recompute_profile
from apps.rooms.models import Room, RoomMember, RoomTransfer

# ---------------------------------------------------------------------------
# 常量（docs/seed-spec.md §2、§3）
# ---------------------------------------------------------------------------

COMPUTER = "计算机学院"
FOREIGN = "外国语学院"
COLLEGES = (COMPUTER, FOREIGN)

STUDENT_PASSWORD = "Demo1234!"
ADMIN_PASSWORD = "Admin1234!"
ADMIN_EMAIL = "admin@cohabit.local"
ADMIN_UID = "0000000099"
ADMIN_NICKNAME = "管理员"

STUDENT_COUNT = 40
SEED_UIDS = tuple(f"{index:010d}" for index in range(1, STUDENT_COUNT + 1))

ROOM_CODES = (
    "100000001",
    "100000002",
    "100000003",
    "100000004",
    "100000005",
    "100000006",
)

INVITE_CODE = "COHAB2026"
INVITE_NOTE = "M1 演示邀请码"
WINDOW_NOTE = "M1 演示窗口（seed）"

WINDOW_CLOSING_DAYS = 7
NOTIFICATION_PER_USER_LIMIT = 5

FORBIDDEN_PAYLOAD_WORDS = ("qq", "wechat", "phone", "contact", "email", "token")

# docs/seed-spec.md §9.1：按学院内序号轮转的 6 个 cohort。
COHORT_HARD: dict[int, dict[str, str]] = {
    1: {
        "smoke": "no",
        "sleep_time": "23_00",
        "wake_time": "7_8",
        "late_return": "rarely",
        "snore": "no",
        "pet": "no_pet",
        "visitor_freq": "never",
        "alcohol": "never",
        "game_noise": "never",
        "ac_temp": "medium",
        "clean_freq": "daily",
    },
    2: {
        "smoke": "no",
        "sleep_time": "00_01",
        "wake_time": "8_9",
        "late_return": "sometimes",
        "snore": "mild",
        "pet": "ok",
        "visitor_freq": "sometimes",
        "alcohol": "social",
        "game_noise": "sometimes",
        "ac_temp": "warm",
        "clean_freq": "weekly",
    },
    3: {
        "smoke": "no",
        "sleep_time": "23_00",
        "wake_time": "7_8",
        "late_return": "rarely",
        "snore": "no",
        "pet": "ok",
        "visitor_freq": "rarely",
        "alcohol": "never",
        "game_noise": "headphones",
        "ac_temp": "medium",
        "clean_freq": "2_3_week",
    },
    4: {
        "smoke": "no",
        "sleep_time": "00_01",
        "wake_time": "8_9",
        "late_return": "sometimes",
        "snore": "no",
        "pet": "ok",
        "visitor_freq": "often",
        "alcohol": "social",
        "game_noise": "sometimes",
        "ac_temp": "medium",
        "clean_freq": "2_3_week",
    },
    5: {
        "smoke": "no",
        "sleep_time": "23_00",
        "wake_time": "7_8",
        "late_return": "rarely",
        "snore": "no",
        "pet": "no_pet",
        "visitor_freq": "rarely",
        "alcohol": "never",
        "game_noise": "headphones",
        "ac_temp": "cool",
        "clean_freq": "daily",
    },
    6: {
        "smoke": "no",
        "sleep_time": "23_00",
        "wake_time": "7_8",
        "late_return": "rarely",
        "snore": "no",
        "pet": "ok",
        "visitor_freq": "rarely",
        "alcohol": "never",
        "game_noise": "never",
        "ac_temp": "medium",
        "clean_freq": "2_3_week",
    },
}

COHORT_SOFT: dict[int, dict[str, int]] = {
    1: {
        "clean": 5,
        "social": 2,
        "noise": 4,
        "boundary": 4,
        "spend": 3,
        "sleep_regular": 5,
    },
    2: {
        "clean": 2,
        "social": 4,
        "noise": 2,
        "boundary": 2,
        "spend": 2,
        "sleep_regular": 2,
    },
    3: {
        "clean": 4,
        "social": 3,
        "noise": 4,
        "boundary": 4,
        "spend": 3,
        "sleep_regular": 4,
    },
    4: {
        "clean": 3,
        "social": 5,
        "noise": 2,
        "boundary": 2,
        "spend": 4,
        "sleep_regular": 3,
    },
    5: {
        "clean": 5,
        "social": 2,
        "noise": 5,
        "boundary": 5,
        "spend": 2,
        "sleep_regular": 4,
    },
    6: {
        "clean": 4,
        "social": 3,
        "noise": 4,
        "boundary": 5,
        "spend": 3,
        "sleep_regular": 4,
    },
}

COHORT_TAGS: dict[int, list[str]] = {
    1: ["早睡早起", "自习搭子", "猫派"],
    2: ["夜猫子", "游戏搭子", "奶茶党"],
    3: ["阅读", "食堂党", "物品归位"],
    4: ["社牛", "喜欢聚餐", "一起运动"],
    5: ["洁癖", "随手收拾", "需要私人空间"],
    6: ["安静独处", "耳机党", "电影迷"],
}

# docs/seed-spec.md §9.5：每院序号 1/7/13/19 追加一个生活标签。
EXTRA_TAGS: dict[int, str] = {1: "咖啡续命", 7: "健身", 13: "徒步", 19: "摄影"}

PROMPT_TEXTS: dict[str, str] = {
    "weekend": "周末我更愿意在图书馆待一天，晚上回来打两把游戏。",
    "small_thing": "关于我的一件小事：我习惯把第二天要穿的衣服提前放好。",
    "vibe": "理想的寝室氛围是安静、干净、互相报备，晚上十一点后不外放。",
    "cannot_accept": "我最不能接受室友在室内吸烟，以及不打招呼带人回来过夜。",
    "visitor_expect": "如果室友带朋友回来，我希望提前半天说一声，尽量在公共区域。",
    "sleep_summary": "用一句话介绍我的作息：十一点前睡、七点半起，周末会补觉。",
}

LONG_VIBE = (
    "理想的寝室氛围是安静、干净、互相报备。晚上十一点后不外放，带朋友回来提前"
    "半天说一声；公共区域轮流打扫，谁的东西谁收拾。遇到作息冲突先商量，不冷战，"
    "也不在群里阴阳怪气。周末可以一起做饭，但别把公共区域当成自己的房间。"
)

# docs/seed-spec.md §9.3：个性覆盖。
PERSONAL: dict[tuple[str, int], dict[str, Any]] = {
    (COMPUTER, 1): {
        "cohort": 3,
        "tags": ["早睡早起", "自习搭子", "物品归位"],
        "prompts": ["small_thing", "vibe"],
        "qq": "100000001",
    },
    (COMPUTER, 9): {
        "cohort": 1,
        "hard": {"clean_freq": "2_3_week"},
        "soft": {"social": 3},
        "tags": ["早睡早起", "自习搭子", "猫派"],
        "prompts": ["weekend", "vibe"],
        "qq": "123456789",
    },
    (COMPUTER, 10): {
        "cohort": 3,
        "hard": {"smoke": "yes"},
        "tags": ["夜猫子", "游戏搭子", "奶茶党"],
    },
    (COMPUTER, 18): {
        "prompts": ["vibe", "weekend"],
        "long_vibe": True,
    },
    (FOREIGN, 11): {
        "cohort": 3,
        "tags": ["阅读", "咖啡续命", "安静独处"],
        "qq": "100000011",
    },
    (FOREIGN, 12): {"qq": "100000012"},
}

# docs/seed-spec.md §9.4：6 人覆盖 9 条红线。
RED_LINES: dict[tuple[str, int], list[str]] = {
    (COMPUTER, 9): ["smoke"],
    (COMPUTER, 10): ["late_return", "game_noise"],
    (COMPUTER, 17): ["snore", "pet"],
    (COMPUTER, 18): ["alcohol", "visitor_freq"],
    (FOREIGN, 4): ["ac_dc", "clean_low"],
    (FOREIGN, 16): ["smoke", "visitor_freq"],
}


@dataclass(frozen=True)
class StudentRow:
    """账号矩阵的一行（docs/seed-spec.md §3）。"""

    college: str
    index: int  # 学院内序号 1..20
    uid: str
    email: str
    nickname: str
    gender: str
    grade: int
    major: str


def build_students() -> list[StudentRow]:
    """按 §3 的固定规则生成 40 名学生（不随机）。"""

    rows: list[StudentRow] = []
    for college_index, college in enumerate(COLLEGES):
        prefix = "小算" if college == COMPUTER else "小外"
        for index in range(1, 21):
            offset = college_index * 20
            uid = f"{offset + index:010d}"
            email = f"demo{offset + index:03d}@stu.edu.cn"
            gender = "MALE" if index <= 10 else "FEMALE"
            if college == COMPUTER:
                major = "软件工程" if index % 2 == 1 else "计算机科学"
            else:
                major = "英语" if index % 2 == 1 else "日语"
            rows.append(
                StudentRow(
                    college=college,
                    index=index,
                    uid=uid,
                    email=email,
                    nickname=f"{prefix}{index:02d}",
                    gender=gender,
                    grade=((index - 1) % 4) + 1,
                    major=major,
                )
            )
    return rows


STUDENTS = build_students()


def _student(college: str, index: int) -> StudentRow:
    for row in STUDENTS:
        if row.college == college and row.index == index:
            return row
    raise CommandError(f"账号矩阵缺少 {college} #{index}")


def profile_payload(college: str, index: int) -> dict[str, Any]:
    """按 §9 生成一个学生的画像原始 JSON（不写 dims/completeness）。"""

    personal = PERSONAL.get((college, index), {})
    cohort = int(personal.get("cohort", ((index - 1) % 6) + 1))
    hard = dict(COHORT_HARD[cohort])
    hard.update(personal.get("hard") or {})
    soft = dict(COHORT_SOFT[cohort])
    soft.update(personal.get("soft") or {})

    tags = list(personal.get("tags") or COHORT_TAGS[cohort])
    if index in EXTRA_TAGS and not personal:
        tags.append(EXTRA_TAGS[index])

    i = index - 1
    prompt_keys = list(personal.get("prompts") or [])
    if not prompt_keys:
        prompt_keys = [PROMPT_ORDER[i % 6], PROMPT_ORDER[(i + 2) % 6]]
        if i in (3, 9, 15):
            prompt_keys.append(PROMPT_ORDER[(i + 4) % 6])
    prompts: dict[str, str] = {}
    for key in prompt_keys:
        text = PROMPT_TEXTS[key]
        if key == "vibe" and personal.get("long_vibe"):
            text = LONG_VIBE
        prompts[key] = text

    return {
        "hard_answers": hard,
        "soft_answers": soft,
        "red_lines": sorted(RED_LINES.get((college, index), []), key=_red_line_key),
        "red_lines_confirmed": True,
        "tags": tags,
        "prompts": prompts,
        "questionnaire_version": QUESTIONNAIRE_VERSION,
    }


def _red_line_key(value: str) -> int:
    from apps.profiles.constants import RED_LINE_ORDER

    return RED_LINE_ORDER.index(value) if value in RED_LINE_ORDER else 99


def contact_payload(college: str, index: int) -> dict[str, Any]:
    """§2.2：仅 §9.3 指定用户填 qq，其余全空。"""

    qq = PERSONAL.get((college, index), {}).get("qq")
    return {
        "qq": qq,
        "wechat": None,
        "phone": None,
        "show_qq": True,
        "show_wechat": False,
        "show_phone": False,
    }


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "生成 M1 演示种子数据（docs/seed-spec.md）"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="删除本命令创建的种子对象后重建",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="显式确认非 DEBUG 环境（生产环境仍会被拒绝）",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="完整执行后回滚，只打印计数",
        )

    # -- 入口 ---------------------------------------------------------------

    def handle(self, *args: Any, **options: Any) -> str:
        self.started_at = timer.perf_counter()
        self.now = timezone.now().replace(second=0, microsecond=0)
        self.skipped_notifications = 0
        self.reset_performed = False

        self._check_environment(bool(options.get("force")))
        self._check_database()

        reset = bool(options.get("reset"))
        already = self._seed_exists()
        if already and not reset:
            raise CommandError(
                "已存在种子数据；使用 --reset 重建",
                returncode=2,
            )

        dry_run = bool(options.get("dry_run"))
        with transaction.atomic():
            if reset:
                self._delete_seed()
            ctx = self._create_all()
            self._assert_invariants(ctx)
            if dry_run:
                transaction.set_rollback(True)

        self._print_summary(ctx, dry_run=dry_run)
        return "seed_demo: ok"

    # -- 守卫 ---------------------------------------------------------------

    def _check_environment(self, force: bool) -> None:
        if settings.DEBUG:
            return
        if not force:
            raise CommandError(
                "seed_demo 拒绝在非 DEBUG 环境执行（如确需，使用 --force）"
            )
        if os.getenv("ENV", "").strip().lower() == "production":
            raise CommandError("seed_demo 拒绝在生产环境执行（ENV=production）")
        host = self._database_host()
        if not _is_local_host(host):
            raise CommandError(
                f"seed_demo 拒绝在非本地数据库执行（host={host or 'unknown'}）"
            )

    @staticmethod
    def _database_host() -> str:
        config = settings.DATABASES.get("default") or {}
        host = str(config.get("HOST") or "")
        if host:
            return host
        raw = os.getenv("DATABASE_URL", "")
        return urlparse(raw).hostname or "" if raw else ""

    def _check_database(self) -> None:
        try:
            User.objects.exists()
        except DatabaseError as exc:  # pragma: no cover - 迁移缺失时触发
            raise CommandError(
                "数据库尚未迁移，请先执行 python manage.py migrate"
            ) from exc

    def _seed_exists(self) -> bool:
        return (
            User.objects.filter(uid__in=SEED_UIDS + (ADMIN_UID,)).exists()
            or Room.objects.filter(code__in=ROOM_CODES).exists()
            or InviteCode.objects.filter(code=INVITE_CODE).exists()
        )

    # -- 删除（§1.4） -------------------------------------------------------

    def _delete_seed(self) -> None:
        seed_users = User.objects.filter(uid__in=SEED_UIDS) | User.objects.filter(
            email=ADMIN_EMAIL
        )
        seed_rooms = Room.objects.filter(code__in=ROOM_CODES)

        Notification.objects.filter(user__in=seed_users).delete()
        Report.objects.filter(reporter__in=seed_users).delete()
        Block.objects.filter(blocker__in=seed_users).delete()
        Block.objects.filter(blocked__in=seed_users).delete()
        RoomTransfer.objects.filter(room__in=seed_rooms).delete()
        ConnectionRequest.objects.filter(
            initiator__in=seed_users, target__in=seed_users
        ).delete()
        ConnectionRequest.objects.filter(room__in=seed_rooms).delete()
        RoomMember.objects.filter(room__in=seed_rooms).delete()
        # 演示账号在手工体验/联调时可能建出种子清单之外的寝室（code ∉ ROOM_CODES）。
        # 这些寝室的房主是种子账号，删除种子账号前必须先连同其成员一起清掉。
        orphan_rooms = Room.objects.filter(owner__in=seed_users).exclude(
            code__in=ROOM_CODES
        )
        RoomMember.objects.filter(room__in=orphan_rooms).delete()
        RoomTransfer.objects.filter(room__in=orphan_rooms).delete()
        orphan_rooms.delete()
        Room.objects.filter(code__in=ROOM_CODES).delete()
        AuditLog.objects.filter(actor__in=seed_users, request_id="").delete()
        Profile.objects.filter(user__in=seed_users).delete()
        ContactInfo.objects.filter(user__in=seed_users).delete()
        InviteCode.objects.filter(code=INVITE_CODE).delete()
        TimeWindow.objects.filter(college__in=COLLEGES).delete()
        User.objects.filter(uid__in=SEED_UIDS).delete()
        User.objects.filter(email=ADMIN_EMAIL).delete()
        self.reset_performed = True

    # -- 创建 ---------------------------------------------------------------

    def _create_all(self) -> dict[str, Any]:
        ctx: dict[str, Any] = {"non_seed_before": self._non_seed_counts()}
        users = self._create_users()
        ctx["users"] = users
        ctx["profiles"] = self._create_profiles(users)
        ctx["contacts"] = self._create_contacts(users)
        rooms = self._create_rooms(users)
        ctx["rooms"] = rooms
        ctx["room_members"] = list(RoomMember.objects.filter(room__in=rooms.values()))
        ctx["requests"] = self._create_requests(users, rooms)
        ctx["transfers"] = self._create_transfers(users, rooms, ctx["requests"])
        ctx["notifications"] = self._create_notifications(users, rooms, ctx)
        ctx["reports"] = self._create_reports(users, rooms)
        ctx["blocks"] = self._create_blocks(users)
        ctx["audits"] = self._create_audits(users, rooms, ctx)
        ctx["windows"] = self._create_windows()
        ctx["invite"] = self._create_invite(users)
        ctx["non_seed_after"] = self._non_seed_counts()
        return ctx

    def _create_users(self) -> dict[str, User]:
        admin = User.objects.create_user(
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            uid=ADMIN_UID,
            nickname=ADMIN_NICKNAME,
            gender=User.Gender.MALE,
            grade=1,
            college=COMPUTER,
            major="软件工程",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
            is_active=True,
            # 演示管理员要能用 /admin/（时间窗、举报处理、邀请码、审计），
            # 因此直接给超级用户权限（docs/seed-spec §2.1 只列了 role/is_staff）。
            is_superuser=True,
        )
        users: dict[str, User] = {"admin": admin}
        # 注册信号会给每个新用户补 Profile/ContactInfo 空壳；按 docs/seed-spec §2.1
        # 管理员不保留画像与联系方式，这里删掉空壳。
        Profile.objects.filter(user=admin).delete()
        ContactInfo.objects.filter(user=admin).delete()
        created: list[User] = []
        for row in STUDENTS:
            user = User.objects.create_user(
                email=row.email,
                password=STUDENT_PASSWORD,
                uid=row.uid,
                nickname=row.nickname,
                gender=row.gender,
                grade=row.grade,
                college=row.college,
                major=row.major,
                role=User.Role.STUDENT,
                status=User.Status.ACTIVE,
            )
            users[row.nickname] = user
            created.append(user)
        User.objects.filter(pk__in=[u.pk for u in created]).update(last_login=None)
        return users

    def _create_profiles(self, users: dict[str, User]) -> list[Profile]:
        profiles: list[Profile] = []
        for row in STUDENTS:
            user = users[row.nickname]
            profile = Profile.objects.get(user=user)
            payload = profile_payload(row.college, row.index)
            profile.hard_answers = payload["hard_answers"]
            profile.soft_answers = payload["soft_answers"]
            profile.red_lines = payload["red_lines"]
            profile.red_lines_confirmed = True
            profile.tags = payload["tags"]
            profile.prompts = payload["prompts"]
            profile.questionnaire_version = payload["questionnaire_version"]
            recompute_profile(profile, save=False)
            profile.save()
            profiles.append(profile)
        return profiles

    def _create_contacts(self, users: dict[str, User]) -> list[ContactInfo]:
        contacts: list[ContactInfo] = []
        for row in STUDENTS:
            user = users[row.nickname]
            contact = ContactInfo.objects.get(user=user)
            payload = contact_payload(row.college, row.index)
            for field, value in payload.items():
                setattr(contact, field, value)
            contact.save()
            contacts.append(contact)
        return contacts

    # -- 寝室 ---------------------------------------------------------------

    def _create_rooms(self, users: dict[str, User]) -> dict[str, Room]:
        rooms: dict[str, Room] = {}
        for spec in _room_specs():
            owner = users[spec["owner"]]
            created_at = self._at(**spec["created_offset"])
            room = Room.objects.create(
                code=spec["code"],
                title=spec["title"],
                owner=owner,
                capacity=spec["capacity"],
                member_count=spec["member_count"],
                gender=spec["gender"],
                college=spec["college"],
                major=owner.major,
                tags=list(spec["tags"]),
                status=spec["status"],
                archived_at=(
                    self._at(**spec["archived_offset"])
                    if spec.get("archived_offset")
                    else None
                ),
                dissolved_at=(
                    self._at(**spec["dissolved_offset"])
                    if spec.get("dissolved_offset")
                    else None
                ),
            )
            _stamp(Room, room.pk, created_at=created_at)
            room.created_at = created_at

            for member_spec in spec["members"]:
                member = RoomMember.objects.create(
                    room=room,
                    user=users[member_spec["nickname"]],
                    role=member_spec.get("role", RoomMember.Role.MEMBER),
                    status=member_spec["status"],
                    left_at=(
                        self._at(**member_spec["left_offset"])
                        if member_spec.get("left_offset")
                        else None
                    ),
                    reason=member_spec.get("reason", ""),
                )
                joined_at = self._at(**member_spec["joined_offset"])
                _stamp(RoomMember, member.pk, created_at=joined_at)
                member.created_at = joined_at
            rooms[spec["code"]] = room
        return rooms

    # -- 请求 ---------------------------------------------------------------

    def _create_requests(
        self,
        users: dict[str, User],
        rooms: dict[str, Room],
    ) -> list[ConnectionRequest]:
        requests: list[ConnectionRequest] = []
        for spec in _request_specs():
            room = rooms[spec["room"]] if spec.get("room") else None
            contact_shared_at = (
                self._at(**spec["shared_offset"]) if spec.get("shared_offset") else None
            )
            initiator_confirm_at = (
                self._at(**spec["init_offset"]) if spec.get("init_offset") else None
            )
            target_confirm_at = (
                self._at(**spec["target_offset"]) if spec.get("target_offset") else None
            )
            expires_at = (
                self._at(**spec["expires_offset"])
                if spec.get("expires_offset")
                else None
            )
            request = ConnectionRequest.objects.create(
                type=ConnectionRequest.Type.INVITE,
                initiator=users[spec["initiator"]],
                target=users[spec["target"]],
                room=room,
                status=spec["status"],
                message=spec["message"],
                capacity_pref=spec["capacity"] if room is None else None,
                contact_shared_at=contact_shared_at,
                initiator_confirm_at=initiator_confirm_at,
                target_confirm_at=target_confirm_at,
                expires_at=expires_at,
                close_reason="",
            )
            created_at = self._at(**spec["created_offset"])
            _stamp(ConnectionRequest, request.pk, created_at=created_at)
            request.created_at = created_at
            requests.append(request)
        return requests

    # -- 转让 ---------------------------------------------------------------

    def _create_transfers(
        self,
        users: dict[str, User],
        rooms: dict[str, Room],
        requests: list[ConnectionRequest],
    ) -> list[RoomTransfer]:
        transfers: list[RoomTransfer] = []
        for spec in _transfer_specs():
            room = rooms[spec["room"]]
            transfer = RoomTransfer.objects.create(
                room=room,
                from_owner=users[spec["from_owner"]],
                to_member=users[spec["to_member"]],
                status=spec["status"],
                expires_at=self._at(**spec["expires_offset"]),
            )
            created_at = self._at(**spec["created_offset"])
            _stamp(RoomTransfer, transfer.pk, created_at=created_at)
            transfer.created_at = created_at
            transfers.append(transfer)
        return transfers

    # -- 通知 ---------------------------------------------------------------

    def _create_notifications(
        self,
        users: dict[str, User],
        rooms: dict[str, Room],
        ctx: dict[str, Any],
    ) -> list[Notification]:
        events = self._notification_events(users, rooms, ctx)
        events.sort(key=lambda item: (item[0], item[1], item[2]))
        per_user: dict[str, int] = {}
        notes: list[Notification] = []
        for at, nickname, type_, payload in events:
            if per_user.get(nickname, 0) >= NOTIFICATION_PER_USER_LIMIT:
                self.skipped_notifications += 1
                continue
            per_user[nickname] = per_user.get(nickname, 0) + 1
            event_at = at.replace(second=0, microsecond=0)
            note = notify(users[nickname], type_, dict(payload))
            read_at = None
            if event_at < self.now - timedelta(days=7):
                read_at = event_at + timedelta(hours=1)
            _stamp(Notification, note.pk, created_at=event_at, read_at=read_at)
            note.created_at = event_at
            note.read_at = read_at
            notes.append(note)
        return notes

    def _notification_events(
        self,
        users: dict[str, User],
        rooms: dict[str, Room],
        ctx: dict[str, Any],
    ) -> list[tuple[datetime, str, str, dict[str, Any]]]:
        events: list[tuple[datetime, str, str, dict[str, Any]]] = []
        method = Notification.Type

        for request in ctx["requests"]:
            initiator = request.initiator
            target = request.target
            created = request.created_at
            events.append(
                (
                    created,
                    target.nickname,
                    method.CONNECTION_RECEIVED,
                    {
                        "connection_id": request.id,
                        "type": request.type,
                        "from_nickname": initiator.nickname,
                    },
                )
            )
            if request.status == ConnectionRequest.Status.PENDING:
                continue
            shared = request.contact_shared_at
            events.append(
                (
                    shared,
                    initiator.nickname,
                    method.CONTACT_SHARED,
                    {"connection_id": request.id},
                )
            )
            if request.status == ConnectionRequest.Status.CONFIRMING:
                first_confirm = request.initiator_confirm_at
                if first_confirm is not None:
                    events.append(
                        (
                            first_confirm,
                            target.nickname,
                            method.CONFIRM_PENDING,
                            {
                                "connection_id": request.id,
                                "nickname": initiator.nickname,
                            },
                        )
                    )
            if request.status == ConnectionRequest.Status.CONFIRMED:
                room = request.room
                confirmed_at = request.target_confirm_at or request.contact_shared_at
                payload = {
                    "connection_id": request.id,
                    "room_code": room.code,
                    "room_title": room.title,
                }
                for party in (initiator, target):
                    events.append(
                        (confirmed_at, party.nickname, method.CONFIRMED, payload)
                    )

        # 寝室事件
        full_room = rooms["100000003"]
        full_at = self._at(days=-24)
        for member in _members(full_room, RoomMember.Status.ACTIVE):
            events.append(
                (
                    full_at,
                    member.user.nickname,
                    method.ROOM_FULL,
                    {"room_code": full_room.code, "capacity": full_room.capacity},
                )
            )

        locked_room = rooms["100000004"]
        locked_at = self._at(days=-2)
        for member in _members(locked_room, RoomMember.Status.ACTIVE):
            events.append(
                (
                    locked_at,
                    member.user.nickname,
                    method.ROOM_LOCKED,
                    {"room_code": locked_room.code},
                )
            )

        archived_room = rooms["100000005"]
        archived_at = archived_room.archived_at or self._at(days=-30)
        for member in _members(archived_room, RoomMember.Status.ARCHIVED):
            events.append(
                (
                    archived_at,
                    member.user.nickname,
                    method.ROOM_ARCHIVED,
                    {
                        "room_code": archived_room.code,
                        "archived_at": _iso(archived_at),
                    },
                )
            )

        dissolved_room = rooms["100000006"]
        dissolved_at = dissolved_room.dissolved_at or self._at(days=-20)
        for member in _members(dissolved_room, RoomMember.Status.LEFT):
            events.append(
                (
                    dissolved_at,
                    member.user.nickname,
                    method.ROOM_DISSOLVED,
                    {"room_code": dissolved_room.code, "reason": "DISSOLVED"},
                )
            )

        # 转让事件
        pending_transfer = next(
            item for item in ctx["transfers"] if item.status == "PENDING"
        )
        events.append(
            (
                self._at(hours=-1),
                pending_transfer.to_member.nickname,
                method.TRANSFER_RECEIVED,
                {
                    "room_code": pending_transfer.room.code,
                    "transfer_id": pending_transfer.id,
                    "from_nickname": pending_transfer.from_owner.nickname,
                    "expires_at": _iso(pending_transfer.expires_at),
                },
            )
        )
        expired_transfer = next(
            item for item in ctx["transfers"] if item.status == "EXPIRED"
        )
        events.append(
            (
                expired_transfer.expires_at,
                expired_transfer.from_owner.nickname,
                method.TRANSFER_EXPIRED,
                {
                    "room_code": expired_transfer.room.code,
                    "transfer_id": expired_transfer.id,
                },
            )
        )

        # #2 入寝事件：12 加入（既有 11），13 加入（既有 11、12）
        room2 = rooms["100000002"]
        joins = [
            (self._at(days=-13), "小外12", 2),
            (self._at(days=-12), "小外13", 3),
        ]
        for at, joiner, count in joins:
            existing = [
                row
                for row in _members(room2, RoomMember.Status.ACTIVE)
                if row.user.nickname != joiner
                and row.created_at.replace(second=0, microsecond=0) <= at
            ]
            for row in existing:
                events.append(
                    (
                        at,
                        row.user.nickname,
                        method.MEMBER_JOINED,
                        {
                            "room_code": room2.code,
                            "nickname": joiner,
                            "member_count": count,
                            "capacity": room2.capacity,
                        },
                    )
                )

        # 窗口提醒：每院全体各 1 条（去重键 college+days）
        window_at = self._at(hours=-1)
        for row in STUDENTS:
            events.append(
                (
                    window_at,
                    row.nickname,
                    method.WINDOW_CLOSING,
                    {"college": row.college, "days": WINDOW_CLOSING_DAYS},
                )
            )
        return events

    # -- 举报 / 拉黑 / 审计 / 窗口 / 邀请码 ---------------------------------

    def _create_reports(
        self,
        users: dict[str, User],
        rooms: dict[str, Room],
    ) -> list[Report]:
        first = Report.objects.create(
            reporter=users["小算07"],
            target_type=Report.TargetType.USER,
            target_id=users["小算08"].pk,
            reason="言语不当（演示数据）",
            status=Report.Status.OPEN,
        )
        second = Report.objects.create(
            reporter=users["小外19"],
            target_type=Report.TargetType.ROOM,
            target_id=rooms["100000004"].pk,
            reason="描述与实际不符（演示数据）",
            status=Report.Status.RESOLVED,
            handled_by=users["admin"],
        )
        return [first, second]

    def _create_blocks(self, users: dict[str, User]) -> list[Block]:
        pairs = [("小算07", "小算08"), ("小外19", "小外20")]
        rows: list[Block] = []
        for left, right in pairs:
            rows.append(Block.objects.create(blocker=users[left], blocked=users[right]))
            rows.append(Block.objects.create(blocker=users[right], blocked=users[left]))
        return rows

    def _create_audits(
        self,
        users: dict[str, User],
        rooms: dict[str, Room],
        ctx: dict[str, Any],
    ) -> list[AuditLog]:
        room1 = rooms["100000001"]
        room2 = rooms["100000002"]
        member12 = RoomMember.objects.get(
            room=room2, user=users["小外12"], status=RoomMember.Status.ACTIVE
        )
        member13 = RoomMember.objects.get(
            room=room2, user=users["小外13"], status=RoomMember.Status.ACTIVE
        )
        entries = [
            (
                "ROOM_CREATED",
                "room",
                room1.pk,
                users["小算01"],
                {"room_code": room1.code, "capacity": room1.capacity},
                self._at(days=-10),
            ),
            (
                "ROOM_CREATED",
                "room",
                room2.pk,
                users["小外11"],
                {"room_code": room2.code, "capacity": room2.capacity},
                self._at(days=-14),
            ),
            (
                "MEMBER_JOINED",
                "room_member",
                member12.pk,
                users["小外12"],
                {"room_id": room2.pk, "user_id": member12.user_id, "role": "MEMBER"},
                self._at(days=-13),
            ),
            (
                "MEMBER_JOINED",
                "room_member",
                member13.pk,
                users["小外13"],
                {"room_id": room2.pk, "user_id": member13.user_id, "role": "MEMBER"},
                self._at(days=-12),
            ),
            (
                "ROOM_LOCKED",
                "room",
                rooms["100000004"].pk,
                users["小外01"],
                {"room_code": "100000004", "from": "RECRUITING"},
                self._at(days=-2),
            ),
            (
                "ROOM_ARCHIVED",
                "room",
                rooms["100000005"].pk,
                users["admin"],
                {"room_code": "100000005", "member_count": 6},
                self._at(days=-30),
            ),
            (
                "ROOM_DISSOLVED",
                "room",
                rooms["100000006"].pk,
                users["小外14"],
                {"room_code": "100000006", "member_count": 0, "reason": "DISSOLVED"},
                self._at(days=-20),
            ),
            (
                "TRANSFER_REQUESTED",
                "transfer",
                ctx["transfers"][0].pk,
                users["小算01"],
                {
                    "room_code": room1.code,
                    "to_member_id": ctx["transfers"][0].to_member_id,
                },
                self._at(hours=-1),
            ),
            (
                "ROOM_UPDATED",
                "room",
                room1.pk,
                users["小算01"],
                {"fields": ["tags"]},
                self._at(days=-8),
            ),
            (
                "USER_REGISTERED",
                "user",
                users["小算01"].pk,
                users["小算01"],
                {"uid": users["小算01"].uid},
                self._at(days=-60),
            ),
        ]
        audits: list[AuditLog] = []
        for action, target_type, target_id, actor, meta, at in entries:
            log = write_audit(
                action,
                target_type,
                target_id,
                actor=actor,
                meta=meta,
                request_id="",
            )
            _stamp(AuditLog, log.pk, created_at=at)
            log.created_at = at
            audits.append(log)
        return audits

    def _create_windows(self) -> list[TimeWindow]:
        local_now = timezone.localtime(self.now)
        start_at = (local_now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_at = (local_now + timedelta(days=7)).replace(
            hour=23, minute=59, second=0, microsecond=0
        )
        windows: list[TimeWindow] = []
        for college in COLLEGES:
            window = TimeWindow.objects.create(
                college=college,
                start_at=start_at,
                end_at=end_at,
                note=WINDOW_NOTE,
            )
            _stamp(TimeWindow, window.pk, created_at=start_at)
            window.created_at = start_at
            windows.append(window)
        return windows

    def _create_invite(self, users: dict[str, User]) -> InviteCode:
        invite = InviteCode.objects.create(
            code=INVITE_CODE,
            note=INVITE_NOTE,
            max_uses=0,
            used_count=0,
            expires_at=self._at(days=30),
            is_active=True,
            created_by=users["admin"],
        )
        return invite

    # -- 工具 ---------------------------------------------------------------

    def _at(self, **offset: int) -> datetime:
        delta = timedelta(
            days=offset.get("days", 0),
            hours=offset.get("hours", 0),
        )
        return self.now + delta

    def _non_seed_counts(self) -> tuple[int, int]:
        seed_users = User.objects.filter(uid__in=SEED_UIDS)
        admin = User.objects.filter(email=ADMIN_EMAIL)
        users = User.objects.exclude(pk__in=seed_users).exclude(pk__in=admin).count()
        rooms = Room.objects.exclude(code__in=ROOM_CODES).count()
        return users, rooms

    # -- 断言（§10） ---------------------------------------------------------

    def _assert_invariants(self, ctx: dict[str, Any]) -> None:
        users = ctx["users"]
        rooms = ctx["rooms"]
        students = [users[row.nickname] for row in STUDENTS]
        student_pks = [user.pk for user in students]

        # I-01 账号
        if len(student_pks) != 40:
            self._fail("I-01", f"students={len(student_pks)}")
        # 只校验本命令创建的种子管理员存在且唯一；运维手工创建的额外 ADMIN
        # 允许存在，且 --reset 不会删除它们。
        if (
            User.objects.filter(
                uid=ADMIN_UID, email=ADMIN_EMAIL, role=User.Role.ADMIN
            ).count()
            != 1
        ):
            self._fail("I-01", "seed admin != 1")
        if len({user.email for user in students}) != 40:
            self._fail("I-01", "duplicate email")

        # I-02 每用户 ≤1 个 ACTIVE 成员关系
        active_members = RoomMember.objects.filter(
            user__in=student_pks, status=RoomMember.Status.ACTIVE
        )
        per_user = {}
        for member in active_members:
            per_user[member.user_id] = per_user.get(member.user_id, 0) + 1
        if any(count > 1 for count in per_user.values()):
            self._fail("I-02", "multiple active rooms")
        if len(per_user) != 12:
            self._fail("I-02", f"active users={len(per_user)}")

        # I-03 非终态 member_count == ACTIVE 成员数
        expected = {
            "100000001": 2,
            "100000002": 3,
            "100000003": 4,
            "100000004": 3,
        }
        for code, count in expected.items():
            room = rooms[code]
            actual = RoomMember.objects.filter(
                room=room, status=RoomMember.Status.ACTIVE
            ).count()
            if room.member_count != count or actual != count:
                self._fail("I-03", f"{code} member_count={room.member_count}/{actual}")

        # I-04 归档房
        archived = rooms["100000005"]
        if archived.member_count != 6:
            self._fail("I-04", f"archived member_count={archived.member_count}")
        if RoomMember.objects.filter(
            room=archived, status=RoomMember.Status.ACTIVE
        ).exists():
            self._fail("I-04", "archived room has ACTIVE member")
        if archived.members.exclude(status=RoomMember.Status.ARCHIVED).exists():
            self._fail("I-04", "archived member status")

        # I-05 解散房
        dissolved = rooms["100000006"]
        if dissolved.member_count != 0 or dissolved.dissolved_at is None:
            self._fail("I-05", f"dissolved member_count={dissolved.member_count}")
        if dissolved.members.exclude(
            status=RoomMember.Status.LEFT, reason=RoomMember.Reason.DISSOLVED
        ).exists():
            self._fail("I-05", "dissolved member status")

        # I-06 每非终态房恰 1 个 ACTIVE OWNER
        for code in ("100000001", "100000002", "100000003", "100000004"):
            owners = RoomMember.objects.filter(
                room=rooms[code],
                role=RoomMember.Role.OWNER,
                status=RoomMember.Status.ACTIVE,
            ).count()
            if owners != 1:
                self._fail("I-06", f"{code} owners={owners}")

        # I-07 code
        codes = sorted(
            Room.objects.filter(code__in=ROOM_CODES).values_list("code", flat=True)
        )
        if codes != sorted(ROOM_CODES):
            self._fail("I-07", f"codes={codes}")

        # I-08 状态分布
        distribution = {
            "RECRUITING": 2,
            "FULL": 1,
            "LOCKED": 1,
            "ARCHIVED": 1,
            "DISSOLVED": 1,
        }
        for status, count in distribution.items():
            actual = Room.objects.filter(code__in=ROOM_CODES, status=status).count()
            if actual != count:
                self._fail("I-08", f"{status}={actual}")

        # I-09 请求数量/状态
        requests = ctx["requests"]
        if len(requests) != 8:
            self._fail("I-09", f"requests={len(requests)}")
        for status, count in {
            "PENDING": 2,
            "CONTACT_SHARED": 2,
            "CONFIRMING": 2,
            "CONFIRMED": 2,
        }.items():
            actual = ConnectionRequest.objects.filter(
                pk__in=[item.pk for item in requests], status=status
            ).count()
            if actual != count:
                self._fail("I-09", f"{status}={actual}")

        # I-10 每院 4 条
        for college in COLLEGES:
            nicknames = [row.nickname for row in STUDENTS if row.college == college]
            actual = ConnectionRequest.objects.filter(
                pk__in=[item.pk for item in requests],
                initiator__nickname__in=nicknames,
            ).count()
            if actual != 4:
                self._fail("I-10", f"{college} requests={actual}")

        # I-11 无重复 open 对
        open_statuses = ("PENDING", "CONTACT_SHARED", "CONFIRMING")
        open_pairs = ConnectionRequest.objects.filter(
            pk__in=[item.pk for item in requests], status__in=open_statuses
        ).values_list("initiator_id", "target_id")
        if len(set(open_pairs)) != len(list(open_pairs)):
            self._fail("I-11", "duplicate open pair")

        # I-12 CONFIRMED 成员一致
        for request in requests:
            if request.status != "CONFIRMED":
                continue
            room = request.room
            for party in (request.initiator, request.target):
                if not RoomMember.objects.filter(
                    room=room, user=party, status=RoomMember.Status.ACTIVE
                ).exists():
                    self._fail("I-12", f"{room.code} missing {party.nickname}")

        # I-13 请求时间字段
        for request in requests:
            if request.status == "PENDING":
                if request.expires_at is None:
                    self._fail("I-13", "pending expires null")
            if request.status == "CONTACT_SHARED":
                delta = request.expires_at - request.contact_shared_at
                if abs(delta - timedelta(days=7)) > timedelta(minutes=1):
                    self._fail("I-13", "contact_shared expires")
            if request.status == "CONFIRMING":
                if request.initiator_confirm_at is None:
                    self._fail("I-13", "confirming initiator_confirm_at null")
                if request.target_confirm_at is not None:
                    self._fail("I-13", "confirming target_confirm_at set")
            if request.status == "CONFIRMED":
                if not (request.initiator_confirm_at and request.target_confirm_at):
                    self._fail("I-13", "confirmed timestamps")
                if request.expires_at is not None:
                    self._fail("I-13", "confirmed expires_at not null")
            if (
                request.contact_shared_at
                and request.created_at > request.contact_shared_at
            ):
                self._fail("I-13", "created_at after contact_shared_at")

        # I-14 转让
        transfers = ctx["transfers"]
        if len(transfers) != 2:
            self._fail("I-14", f"transfers={len(transfers)}")
        pending = [item for item in transfers if item.status == "PENDING"]
        expired = [item for item in transfers if item.status == "EXPIRED"]
        if len(pending) != 1 or len(expired) != 1:
            self._fail("I-14", "transfer status")
        if not RoomMember.objects.filter(
            room=pending[0].room,
            user=pending[0].to_member,
            status=RoomMember.Status.ACTIVE,
        ).exists():
            self._fail("I-14", "pending transfer target not active member")
        if not expired[0].expires_at < self.now:
            self._fail("I-14", "expired transfer expires_at future")
        if pending[0].room.owner_id != pending[0].from_owner_id:
            self._fail("I-14", "owner changed")

        # I-15 通知
        notes = ctx["notifications"]
        counts: dict[int, int] = {}
        for note in notes:
            counts[note.user_id] = counts.get(note.user_id, 0) + 1
        if any(count > NOTIFICATION_PER_USER_LIMIT for count in counts.values()):
            self._fail("I-15", "notification per user > limit")
        if not set(counts).issubset(set(student_pks)):
            self._fail("I-15", "notification recipient not seed student")
        if len({note.type for note in notes}) < 10:
            self._fail("I-15", "notification types < 10")
        for note in notes:
            text = f"{note.payload}"
            for word in FORBIDDEN_PAYLOAD_WORDS:
                if word in text:
                    self._fail("I-15", f"payload contains {word}")

        # I-16 画像
        profiles = ctx["profiles"]
        if len(profiles) != 40:
            self._fail("I-16", f"profiles={len(profiles)}")
        for profile in profiles:
            if profile.completeness != 100:
                self._fail("I-16", f"{profile.user_id} completeness")
            if len(profile.hard_answers or {}) != 11:
                self._fail("I-16", "hard keys")
            if len(profile.soft_answers or {}) != 6:
                self._fail("I-16", "soft keys")
            if not 3 <= len(profile.tags or []) <= 8:
                self._fail("I-16", "tags count")
            if not 2 <= len(profile.prompts or {}) <= 3:
                self._fail("I-16", "prompts count")
            if profile.red_lines_confirmed is not True:
                self._fail("I-16", "red_lines_confirmed")

        # I-17 dims
        for profile in profiles:
            dims = profile.dims or {}
            expected_dims = compute_dims(profile.hard_answers, profile.soft_answers)
            if dims != expected_dims:
                self._fail("I-17", f"{profile.user_id} dims mismatch")
            if len(dims) != 6 or any(not 0 <= value <= 100 for value in dims.values()):
                self._fail("I-17", "dims range")

        # I-18 时间窗
        windows = ctx["windows"]
        if len(windows) != 2:
            self._fail("I-18", f"windows={len(windows)}")
        if {window.college for window in windows} != set(COLLEGES):
            self._fail("I-18", "window colleges")
        for window in windows:
            if not window.start_at < window.end_at:
                self._fail("I-18", "window range")
            if not window.start_at <= self.now <= window.end_at:
                self._fail("I-18", "window not open now")

        # I-19 邀请码
        invite = ctx["invite"]
        if invite.code != INVITE_CODE or invite.max_uses != 0 or not invite.is_active:
            self._fail("I-19", "invite code")

        # I-20 举报/拉黑
        reports = ctx["reports"]
        if len(reports) != 2:
            self._fail("I-20", f"reports={len(reports)}")
        if {report.status for report in reports} != {"OPEN", "RESOLVED"}:
            self._fail("I-20", "report status")
        if any(report.target_id is None for report in reports):
            self._fail("I-20", "report target_id null")
        if len(ctx["blocks"]) != 4:
            self._fail("I-20", f"blocks={len(ctx['blocks'])}")

        # I-21 隐私
        if (
            ContactInfo.objects.filter(user__in=student_pks)
            .exclude(phone=None)
            .exists()
        ):
            self._fail("I-21", "phone not empty")

        # I-22 非种子数据不变
        if ctx["non_seed_before"] != ctx["non_seed_after"]:
            self._fail("I-22", "non-seed data changed")

    @staticmethod
    def _fail(key: str, detail: str) -> None:
        raise CommandError(f"seed_demo 自检失败：#{key} {detail}")

    # -- 输出（§12） ---------------------------------------------------------

    def _print_summary(self, ctx: dict[str, Any], *, dry_run: bool) -> None:
        users = ctx["users"]
        rooms = ctx["rooms"]
        notes = ctx["notifications"]
        read = sum(1 for note in notes if note.read_at is not None)
        room_status = Counter(room.status for room in rooms.values())
        member_status = Counter(item.status for item in ctx["room_members"])
        request_status = Counter(item.status for item in ctx["requests"])
        transfer_status = Counter(item.status for item in ctx["transfers"])
        with_qq = sum(1 for item in ctx["contacts"] if item.qq)

        elapsed = timer.perf_counter() - self.started_at
        prefix = "（dry-run，已回滚）" if dry_run else ""
        lines = [
            f"seed_demo: ok {prefix}".rstrip(),
            f"  users={len(users)} (students={len(STUDENTS)}, admin=1)",
            f"  profiles={len(ctx['profiles'])} (completeness=100 all)",
            f"  contact_infos={len(ctx['contacts'])} (with_qq={with_qq})",
            "  rooms={} (RECRUITING={} FULL={} LOCKED={} ARCHIVED={} DISSOLVED={})".format(
                len(rooms),
                room_status["RECRUITING"],
                room_status["FULL"],
                room_status["LOCKED"],
                room_status["ARCHIVED"],
                room_status["DISSOLVED"],
            ),
            "  room_members={} (ACTIVE={} ARCHIVED={} LEFT={})".format(
                sum(member_status.values()),
                member_status["ACTIVE"],
                member_status["ARCHIVED"],
                member_status["LEFT"],
            ),
            "  requests={} (PENDING={} CONTACT_SHARED={} CONFIRMING={} CONFIRMED={})".format(
                len(ctx["requests"]),
                request_status["PENDING"],
                request_status["CONTACT_SHARED"],
                request_status["CONFIRMING"],
                request_status["CONFIRMED"],
            ),
            "  transfers={} (PENDING={} EXPIRED={})".format(
                len(ctx["transfers"]),
                transfer_status["PENDING"],
                transfer_status["EXPIRED"],
            ),
            "  notifications={} (read={} unread={}; types={}; skipped={})".format(
                len(notes),
                read,
                len(notes) - read,
                len({note.type for note in notes}),
                self.skipped_notifications,
            ),
            "  windows={} invite_codes=1 reports={} blocks={} audits={}".format(
                len(ctx["windows"]),
                len(ctx["reports"]),
                len(ctx["blocks"]),
                len(ctx["audits"]),
            ),
            f"  elapsed={elapsed:.1f}s",
        ]
        for line in lines:
            self.stdout.write(line)


# ---------------------------------------------------------------------------
# 数据矩阵
# ---------------------------------------------------------------------------


def _room_specs() -> list[dict[str, Any]]:
    """§4 寝室矩阵（固定 6 间）。"""

    return [
        {
            "code": "100000001",
            "college": COMPUTER,
            "gender": "MALE",
            "capacity": 4,
            "status": Room.Status.RECRUITING,
            "member_count": 2,
            "owner": "小算01",
            "title": "小算01的寝室",
            "tags": ["早睡早起", "自习搭子"],
            "created_offset": {"days": -10},
            "members": [
                {
                    "nickname": "小算01",
                    "role": RoomMember.Role.OWNER,
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -10},
                },
                {
                    "nickname": "小算02",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -9},
                },
            ],
        },
        {
            "code": "100000002",
            "college": FOREIGN,
            "gender": "FEMALE",
            "capacity": 6,
            "status": Room.Status.RECRUITING,
            "member_count": 3,
            "owner": "小外11",
            "title": "小外11的寝室",
            "tags": ["阅读", "咖啡续命", "安静独处"],
            "created_offset": {"days": -14},
            "members": [
                {
                    "nickname": "小外11",
                    "role": RoomMember.Role.OWNER,
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -14},
                },
                {
                    "nickname": "小外12",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -13},
                },
                {
                    "nickname": "小外13",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -12},
                },
            ],
        },
        {
            "code": "100000003",
            "college": COMPUTER,
            "gender": "MALE",
            "capacity": 4,
            "status": Room.Status.FULL,
            "member_count": 4,
            "owner": "小算03",
            "title": "小算03的寝室",
            "tags": ["健身", "早起学习", "食堂党"],
            "created_offset": {"days": -25},
            "members": [
                {
                    "nickname": "小算03",
                    "role": RoomMember.Role.OWNER,
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -25},
                },
                {
                    "nickname": "小算04",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -24},
                },
                {
                    "nickname": "小算05",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -23},
                },
                {
                    "nickname": "小算06",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -22},
                },
            ],
        },
        {
            "code": "100000004",
            "college": FOREIGN,
            "gender": "MALE",
            "capacity": 4,
            "status": Room.Status.LOCKED,
            "member_count": 3,
            "owner": "小外01",
            "title": "小外01的寝室",
            "tags": ["二次元", "电影迷", "奶茶党"],
            "created_offset": {"days": -5},
            "members": [
                {
                    "nickname": "小外01",
                    "role": RoomMember.Role.OWNER,
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -5},
                },
                {
                    "nickname": "小外02",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -4},
                },
                {
                    "nickname": "小外03",
                    "status": RoomMember.Status.ACTIVE,
                    "joined_offset": {"days": -4, "hours": 1},
                },
            ],
        },
        {
            "code": "100000005",
            "college": COMPUTER,
            "gender": "FEMALE",
            "capacity": 6,
            "status": Room.Status.ARCHIVED,
            "member_count": 6,
            "owner": "小算11",
            "title": "小算11的寝室",
            "tags": ["猫派", "阅读", "物品归位"],
            "created_offset": {"days": -45},
            "archived_offset": {"days": -30},
            "members": [
                {
                    "nickname": "小算11",
                    "role": RoomMember.Role.OWNER,
                    "status": RoomMember.Status.ARCHIVED,
                    "reason": RoomMember.Reason.ARCHIVED,
                    "joined_offset": {"days": -45},
                    "left_offset": {"days": -30},
                },
                {
                    "nickname": "小算12",
                    "status": RoomMember.Status.ARCHIVED,
                    "reason": RoomMember.Reason.ARCHIVED,
                    "joined_offset": {"days": -44},
                    "left_offset": {"days": -30},
                },
                {
                    "nickname": "小算13",
                    "status": RoomMember.Status.ARCHIVED,
                    "reason": RoomMember.Reason.ARCHIVED,
                    "joined_offset": {"days": -43},
                    "left_offset": {"days": -30},
                },
                {
                    "nickname": "小算14",
                    "status": RoomMember.Status.ARCHIVED,
                    "reason": RoomMember.Reason.ARCHIVED,
                    "joined_offset": {"days": -42},
                    "left_offset": {"days": -30},
                },
                {
                    "nickname": "小算15",
                    "status": RoomMember.Status.ARCHIVED,
                    "reason": RoomMember.Reason.ARCHIVED,
                    "joined_offset": {"days": -41},
                    "left_offset": {"days": -30},
                },
                {
                    "nickname": "小算16",
                    "status": RoomMember.Status.ARCHIVED,
                    "reason": RoomMember.Reason.ARCHIVED,
                    "joined_offset": {"days": -40},
                    "left_offset": {"days": -30},
                },
            ],
        },
        {
            "code": "100000006",
            "college": FOREIGN,
            "gender": "FEMALE",
            "capacity": 2,
            "status": Room.Status.DISSOLVED,
            "member_count": 0,
            "owner": "小外14",
            "title": "小外14的寝室",
            "tags": ["音乐现场", "摄影"],
            "created_offset": {"days": -40},
            "archived_offset": {"days": -20},
            "dissolved_offset": {"days": -20},
            "members": [
                {
                    "nickname": "小外14",
                    "role": RoomMember.Role.OWNER,
                    "status": RoomMember.Status.LEFT,
                    "reason": RoomMember.Reason.DISSOLVED,
                    "joined_offset": {"days": -40},
                    "left_offset": {"days": -20},
                },
                {
                    "nickname": "小外15",
                    "status": RoomMember.Status.LEFT,
                    "reason": RoomMember.Reason.DISSOLVED,
                    "joined_offset": {"days": -40},
                    "left_offset": {"days": -20},
                },
            ],
        },
    ]


def _request_specs() -> list[dict[str, Any]]:
    """§5 请求矩阵（8 条，每院 4 条、状态各 1 条）。"""

    return [
        {
            "initiator": "小算01",
            "target": "小算02",
            "capacity": 4,
            "status": ConnectionRequest.Status.CONFIRMED,
            "room": "100000001",
            "created_offset": {"days": -10},
            "shared_offset": {"days": -10},
            "init_offset": {"days": -10},
            "target_offset": {"days": -9},
            "message": "我们作息和整洁习惯都挺接近，想一起组个 4 人寝。",
        },
        {
            "initiator": "小算17",
            "target": "小算18",
            "capacity": 4,
            "status": ConnectionRequest.Status.CONFIRMING,
            "created_offset": {"days": -2},
            "shared_offset": {"days": -2},
            "init_offset": {"days": -1},
            "expires_offset": {"hours": 24},
            "message": "看了你的作息和标签，感觉挺合拍，想聊聊看。",
        },
        {
            "initiator": "小算19",
            "target": "小算20",
            "capacity": 6,
            "status": ConnectionRequest.Status.CONTACT_SHARED,
            "created_offset": {"days": -3},
            "shared_offset": {"days": -3},
            "expires_offset": {"days": 4},
            "message": "我比较安静、爱整理，想找同样早睡的室友。",
        },
        {
            "initiator": "小算11",
            "target": "小算12",
            "capacity": 4,
            "status": ConnectionRequest.Status.PENDING,
            "created_offset": {"hours": -1},
            "expires_offset": {"hours": 48},
            "message": "想了解一下你的作息，方便的话聊聊？",
        },
        {
            "initiator": "小外11",
            "target": "小外12",
            "capacity": 6,
            "status": ConnectionRequest.Status.CONFIRMED,
            "room": "100000002",
            "created_offset": {"days": -14},
            "shared_offset": {"days": -14},
            "init_offset": {"days": -14},
            "target_offset": {"days": -13},
            "message": "同学院同作息，想一起把寝室定下来。",
        },
        {
            "initiator": "小外16",
            "target": "小外17",
            "capacity": 4,
            "status": ConnectionRequest.Status.CONFIRMING,
            "created_offset": {"days": -2},
            "shared_offset": {"days": -2},
            "init_offset": {"days": -1},
            "expires_offset": {"hours": 24},
            "message": "你列表里也选了早起，想认识一下。",
        },
        {
            "initiator": "小外18",
            "target": "小外19",
            "capacity": 2,
            "status": ConnectionRequest.Status.CONTACT_SHARED,
            "created_offset": {"days": -6},
            "shared_offset": {"days": -6},
            "expires_offset": {"days": 1},
            "message": "喜欢阅读和咖啡，想找安静的室友。",
        },
        {
            "initiator": "小外04",
            "target": "小外05",
            "capacity": 4,
            "status": ConnectionRequest.Status.PENDING,
            "created_offset": {"hours": -1},
            "expires_offset": {"hours": 48},
            "message": "我作息规律、爱干净，想先聊聊。",
        },
    ]


def _transfer_specs() -> list[dict[str, Any]]:
    """§6 转让矩阵（2 条）。"""

    return [
        {
            "room": "100000001",
            "from_owner": "小算01",
            "to_member": "小算02",
            "status": RoomTransfer.Status.PENDING,
            "created_offset": {"hours": -1},
            "expires_offset": {"hours": 23},
        },
        {
            "room": "100000002",
            "from_owner": "小外11",
            "to_member": "小外12",
            "status": RoomTransfer.Status.EXPIRED,
            "created_offset": {"days": -2},
            "expires_offset": {"days": -1},
        },
    ]


def _members(room: Room, status: str) -> list[RoomMember]:
    return list(
        RoomMember.objects.select_related("user")
        .filter(room=room, status=status)
        .order_by("created_at", "pk")
    )


def _stamp(model: Any, pk: int, **fields: Any) -> None:
    model.objects.filter(pk=pk).update(**fields)


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return timezone.localtime(value).isoformat().replace("+00:00", "Z")


def _is_local_host(host: str) -> bool:
    host = (host or "").strip().lower()
    if not host:
        return True
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "db", "postgres"}
