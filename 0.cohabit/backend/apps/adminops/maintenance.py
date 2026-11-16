"""cron 维护任务（docs/02 §3.6/§7.4/§7.5/§8.1；docs/06 M5 W-05…W-10、T-08、R-15…R-17、S-15）。

设计约束：

* 本模块只**编排**已有服务（``connections.services.expire_due_connections``、
  ``rooms.services.archive_room``、``rooms.transfer_services.expire_due_transfers``、
  ``rooms.services.repair_member_count``），事务与锁顺序沿用 M4 约定
  （docs/02 §11.2：TimeWindow → User → ConnectionRequest → Room → Transfer → Member）；
* 每个函数返回 ``dict[str, int | bool]`` 计数，``dry_run=True`` 时只统计不写入，
  方便 cron 日志与测试断言；
* 全部任务可重复执行（W-06）：第二次运行 ``closed/expired/archived/sent`` 均为 0；
* 指令层（``apps/core/management/commands/``）只做参数解析与输出。
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.adminops.models import TimeWindow
from apps.connections.models import OPEN_STATUSES, ConnectionRequest
from apps.core.audit import write_audit
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.rooms.models import Room, RoomMember, RoomTransfer
from apps.rooms.utils import isoformat

# --------------------------------------------------------------------------- #
# 常量（docs/02 §3.6/§7.4/§7.5/§8.1）
# --------------------------------------------------------------------------- #

BATCH_LIMIT = 500
"""单个命令一次最多处理的请求/房间行数（cron 每 10 分钟一轮）。"""

READ_RETENTION_DAYS = 90
"""已读通知保留天数（docs/02 §8.1）。"""

UNREAD_RETENTION_DAYS = 180
"""未读通知保留天数（docs/02 §8.1）。"""

REMINDER_DAYS = (7, 3, 1)
"""窗口关闭提醒：结束前 7/3/1 天各一次（docs/02 §7.5）。"""

ARCHIVABLE_ROOM_STATUSES = (
    Room.Status.RECRUITING,
    Room.Status.FULL,
    Room.Status.LOCKED,
)
"""窗口结束时需要归档的房间状态；ARCHIVED/DISSOLVED 是终态，跳过（docs/02 §7.4）。"""


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _now(at: datetime | None = None) -> datetime:
    if at is None:
        return timezone.now()
    if timezone.is_naive(at):
        return timezone.make_aware(at, timezone.get_current_timezone())
    return at


def _days_left(end_at: datetime, moment: datetime) -> int:
    """剩余天数（向上取整，最少 1）；每日 cron 的天数阈值即基于此。"""
    remaining = (end_at - moment).total_seconds()
    return max(1, math.ceil(remaining / 86400))


def format_stats(name: str, stats: dict[str, Any]) -> str:
    """命令输出格式：``name: key=value key=value``（便于 cron 日志）。"""
    pairs = " ".join(f"{key}={value}" for key, value in stats.items())
    return f"{name}: {pairs}"


def _request_payload(row: ConnectionRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "connection_id": row.pk,
        "reason": ConnectionRequest.CloseReason.TIMEOUT,
    }
    if row.room_id is not None:
        payload["room_code"] = row.room.code
    return payload


# --------------------------------------------------------------------------- #
# 1. expire_connections
# --------------------------------------------------------------------------- #
def expire_connections(
    now: datetime | None = None,
    *,
    limit: int = BATCH_LIMIT,
    dry_run: bool = False,
    request_id: str = "",
) -> dict[str, Any]:
    """关闭到期的在途请求（``EXPIRED/TIMEOUT``，docs/02 §3.6）。"""
    from apps.connections.services import expire_due_connections

    moment = _now(now)
    due = ConnectionRequest.objects.filter(
        status__in=OPEN_STATUSES,
        expires_at__lte=moment,
    ).count()
    if dry_run:
        return {"due": due, "closed": 0, "remaining": due, "dry_run": True}

    closed = expire_due_connections(moment, limit=limit, request_id=request_id)
    remaining = ConnectionRequest.objects.filter(
        status__in=OPEN_STATUSES,
        expires_at__lte=moment,
    ).count()
    return {"due": due, "closed": closed, "remaining": remaining, "dry_run": False}


# --------------------------------------------------------------------------- #
# 2. archive_rooms
# --------------------------------------------------------------------------- #
def _expire_requests_for_colleges(
    colleges: list[str],
    moment: datetime,
    *,
    request_id: str = "",
) -> int:
    """窗口结束时强制关闭该学院的在途请求（``EXPIRED/TIMEOUT``）。

    ``expire_due_connections`` 只处理 ``expires_at <= now`` 的行；docs/02 §7.4
    要求窗口结束时**不等到各自 48h/7d**，因此这里对 ``end_at`` 已达的学院做
    一次强制过期，语义与 :func:`apps.connections.services._expire_if_due` 一致
    （``EXPIRED`` + ``TIMEOUT`` + 双方 ``SYSTEM`` + 审计 ``CONNECTION_EXPIRED``）。
    """
    if not colleges:
        return 0
    ids = list(
        ConnectionRequest.objects.filter(status__in=OPEN_STATUSES)
        .filter(
            Q(initiator__college__in=colleges) | Q(target__college__in=colleges),
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    closed = 0
    for pk in ids:
        with transaction.atomic():
            row = (
                ConnectionRequest.objects.select_for_update(of=("self",))
                .select_related("initiator", "target", "room")
                .filter(pk=pk)
                .first()
            )
            if row is None or row.status not in OPEN_STATUSES:
                continue
            previous = row.status
            row.status = ConnectionRequest.Status.EXPIRED
            row.close_reason = ConnectionRequest.CloseReason.TIMEOUT
            row.closed_by = None
            row.version = (row.version or 0) + 1
            row.save(
                update_fields=[
                    "status",
                    "close_reason",
                    "closed_by",
                    "version",
                    "updated_at",
                ]
            )
            payload = _request_payload(row)
            for party in (row.initiator, row.target):
                notify(party, Notification.Type.SYSTEM, payload)
            write_audit(
                "CONNECTION_EXPIRED",
                "connection",
                row.pk,
                actor=None,
                meta={"reason": "TIMEOUT", "from_status": previous},
                request_id=request_id,
            )
            closed += 1
    return closed


def archive_rooms(
    now: datetime | None = None,
    *,
    limit: int = BATCH_LIMIT,
    dry_run: bool = False,
    request_id: str = "",
) -> dict[str, Any]:
    """窗口结束归档：先过期在途请求，再归档非终态寝室（docs/02 §7.4）。

    顺序即 W-05：``expire_connections``（``EXPIRED/TIMEOUT``）→ ``archive_rooms``
    （``ARCHIVED``）；幂等（W-06）；``DISSOLVED`` 跳过（R-17）；延长窗口不归档
    （W-10：归档前二次校验 ``end_at`` 仍已结束）。
    """
    from apps.rooms.exceptions import InvalidState, RoomNotFound
    from apps.rooms.services import archive_room

    moment = _now(now)
    windows = list(
        TimeWindow.objects.filter(end_at__lte=moment).order_by("college", "end_at")
    )
    colleges = sorted({window.college for window in windows})
    window_end = {window.college: window.end_at for window in windows}

    rooms = list(
        Room.objects.filter(
            college__in=colleges,
            status__in=ARCHIVABLE_ROOM_STATUSES,
        )
        .order_by("pk")
        .values_list("pk", "college")[:limit]
    )
    open_requests = (
        ConnectionRequest.objects.filter(status__in=OPEN_STATUSES)
        .filter(Q(initiator__college__in=colleges) | Q(target__college__in=colleges))
        .count()
    )
    pending_transfers = RoomTransfer.objects.filter(
        status=RoomTransfer.Status.PENDING,
        room__college__in=colleges,
    ).count()

    stats: dict[str, Any] = {
        "windows": len(windows),
        "colleges": len(colleges),
        "rooms": len(rooms),
        "requests": open_requests,
        "transfers": pending_transfers,
        "expired": 0,
        "archived": 0,
        "skipped": 0,
        "remaining_rooms": len(rooms),
        "dry_run": dry_run,
    }
    if dry_run:
        return stats

    # 第 1 步：窗口结束 → 该学院在途请求 EXPIRED/TIMEOUT（不等到各自 48h/7d）。
    stats["expired"] = _expire_requests_for_colleges(
        colleges,
        moment,
        request_id=request_id,
    )

    # 第 2 步：归档 RECRUITING/FULL/LOCKED；DISSOLVED/ARCHIVED 直接跳过。
    archived = 0
    skipped = 0
    for room_pk, college in rooms:
        if not TimeWindow.objects.filter(college=college, end_at__lte=moment).exists():
            # W-10：窗口被延长（end_at 又回到未来）时不归档。
            skipped += 1
            continue
        try:
            archive_room(
                room_pk,
                window_end=window_end.get(college),
                request_id=request_id,
            )
        except (InvalidState, RoomNotFound):
            skipped += 1
        else:
            archived += 1
    stats["archived"] = archived
    stats["skipped"] = skipped
    stats["remaining_rooms"] = Room.objects.filter(
        college__in=colleges,
        status__in=ARCHIVABLE_ROOM_STATUSES,
    ).count()
    return stats


# --------------------------------------------------------------------------- #
# 3. send_window_reminders
# --------------------------------------------------------------------------- #
def _reminder_recipients(college: str) -> list[Any]:
    """该学院有 ACTIVE 寝室或 open 请求的 ACTIVE 用户（docs/02 §7.5 / N-18）。"""
    from apps.accounts.models import User

    room_user_ids = RoomMember.objects.filter(
        status=RoomMember.Status.ACTIVE,
        room__college=college,
    ).values_list("user_id", flat=True)
    request_pairs = (
        ConnectionRequest.objects.filter(status__in=OPEN_STATUSES)
        .filter(Q(initiator__college=college) | Q(target__college=college))
        .values_list("initiator_id", "target_id")
    )
    ids: set[int] = set(room_user_ids)
    for initiator_id, target_id in request_pairs:
        ids.add(initiator_id)
        ids.add(target_id)
    if not ids:
        return []
    return list(
        User.objects.filter(pk__in=ids, status=User.Status.ACTIVE).order_by("pk")
    )


def _sent_reminder_keys(
    user_ids: list[int],
) -> set[tuple[int, str, Any]]:
    """已发送的提醒去重键 ``(user_id, end_at, days_left)``。

    docs/02 §7.5 要求 7/3/1 天各一条，因此去重键必须带 ``days_left``；
    payload 里的 ``end_at`` 用 :func:`apps.rooms.utils.isoformat` 规范化。
    """
    if not user_ids:
        return set()
    rows = Notification.objects.filter(
        user_id__in=user_ids,
        type=Notification.Type.WINDOW_CLOSING,
    ).values_list("user_id", "payload")
    keys: set[tuple[int, str, Any]] = set()
    for user_id, payload in rows:
        if not isinstance(payload, dict):
            continue
        keys.add((user_id, str(payload.get("end_at") or ""), payload.get("days_left")))
    return keys


def send_window_reminders(
    now: datetime | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """结束前 7/3/1 天发送一次 ``WINDOW_CLOSING``（docs/02 §7.5、W-07）。"""
    moment = _now(now)
    windows = list(TimeWindow.objects.filter(end_at__gt=moment).order_by("college"))
    stats: dict[str, Any] = {
        "windows": len(windows),
        "due": 0,
        "sent": 0,
        "skipped": 0,
        "dry_run": dry_run,
    }
    for window in windows:
        days_left = _days_left(window.end_at, moment)
        if days_left not in REMINDER_DAYS:
            continue
        recipients = _reminder_recipients(window.college)
        if not recipients:
            continue
        end_iso = isoformat(window.end_at)
        sent_keys = _sent_reminder_keys([user.pk for user in recipients])
        payload = {
            "college": window.college,
            "end_at": end_iso,
            "days_left": days_left,
        }
        for user in recipients:
            if (user.pk, end_iso, days_left) in sent_keys:
                stats["skipped"] += 1
                continue
            stats["due"] += 1
            if dry_run:
                continue
            notify(user, Notification.Type.WINDOW_CLOSING, payload)
            stats["sent"] += 1
    return stats


# --------------------------------------------------------------------------- #
# 4. cleanup_notifications
# --------------------------------------------------------------------------- #
def _delete_in_batches(queryset: Any, batch: int) -> int:
    total = 0
    while batch > 0:
        ids = list(queryset.order_by("pk").values_list("pk", flat=True)[:batch])
        if not ids:
            break
        deleted, _ = Notification.objects.filter(pk__in=ids).delete()
        total += deleted
        if len(ids) < batch:
            break
    return total


def cleanup_notifications(
    now: datetime | None = None,
    *,
    read_days: int = READ_RETENTION_DAYS,
    unread_days: int = UNREAD_RETENTION_DAYS,
    batch: int = BATCH_LIMIT,
    dry_run: bool = False,
) -> dict[str, Any]:
    """清理过期的站内信；审计不受影响（docs/02 §8.1、D-20）。"""
    moment = _now(now)
    read_due = Notification.objects.filter(
        read_at__isnull=False,
        read_at__lte=moment - timedelta(days=read_days),
    )
    unread_due = Notification.objects.filter(
        read_at__isnull=True,
        created_at__lte=moment - timedelta(days=unread_days),
    )
    stats: dict[str, Any] = {
        "read_due": read_due.count(),
        "unread_due": unread_due.count(),
        "read_deleted": 0,
        "unread_deleted": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return stats
    stats["read_deleted"] = _delete_in_batches(read_due, batch)
    stats["unread_deleted"] = _delete_in_batches(unread_due, batch)
    return stats


# --------------------------------------------------------------------------- #
# 5. expire_transfers
# --------------------------------------------------------------------------- #
def expire_transfers(
    now: datetime | None = None,
    *,
    limit: int = BATCH_LIMIT,
    dry_run: bool = False,
    request_id: str = "",
) -> dict[str, Any]:
    """超过 24h 的 PENDING 转让置 ``EXPIRED`` 并通知双方（docs/02 §6、T-07）。"""
    from apps.rooms.transfer_services import expire_due_transfers

    moment = _now(now)
    due = RoomTransfer.objects.filter(
        status=RoomTransfer.Status.PENDING,
        expires_at__lte=moment,
    ).count()
    if dry_run:
        return {"due": due, "expired": 0, "remaining": due, "dry_run": True}

    expired = expire_due_transfers(moment, limit=limit, request_id=request_id)
    remaining = RoomTransfer.objects.filter(
        status=RoomTransfer.Status.PENDING,
        expires_at__lte=moment,
    ).count()
    return {"due": due, "expired": expired, "remaining": remaining, "dry_run": False}


# --------------------------------------------------------------------------- #
# 6. repair_member_count
# --------------------------------------------------------------------------- #
def repair_member_counts(
    room_id: Any = None,
    *,
    dry_run: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    """检测并修复 ``Room.member_count`` 漂移（docs/06 S-15）。"""
    from django.db.models import Count, Q

    from apps.rooms.services import repair_member_count

    rooms = Room.objects.filter(
        status__in=(Room.Status.RECRUITING, Room.Status.FULL, Room.Status.LOCKED)
    )
    if room_id is not None:
        rooms = rooms.filter(pk=room_id)
    if not dry_run:
        result = repair_member_count(room_id)
        return {**result, "drift": 0, "samples": "", "dry_run": False}

    annotated = rooms.annotate(
        active_members=Count(
            "members",
            filter=Q(members__status=RoomMember.Status.ACTIVE),
        )
    )
    checked = 0
    drift = 0
    samples: list[str] = []
    for pk, stored, actual in annotated.order_by("pk").values_list(
        "pk",
        "member_count",
        "active_members",
    ):
        checked += 1
        if stored == actual:
            continue
        drift += 1
        if len(samples) < limit:
            samples.append(f"{pk}:{stored}->{actual}")
    return {
        "checked": checked,
        "repaired": 0,
        "drift": drift,
        "samples": ",".join(samples),
        "dry_run": True,
    }
