"""adminops 安全服务：举报与拉黑（docs/04 §4.6、docs/02 §3.9/§9.2）。

- 举报只落 ``Report`` 行：不自动封禁、不通知被举报人、不提供学生端列表。
- 拉黑在同一事务内清理双方在途请求（``CANCELLED/BLOCKED``）并写通知与审计；
  已成立寝室保留（02 X-30），不自动解散。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework import status

from apps.accounts.exceptions import ApiError
from apps.accounts.models import User
from apps.connections.models import OPEN_STATUSES, ConnectionRequest
from apps.core.audit import write_audit
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.rooms.locking import lock_requests, lock_users

from .models import Block, Report

REPORT_DAILY_LIMIT = 10
BLOCK_AUDIT_ACTION = "CONNECTION_BLOCKED"


class SafetyError(ApiError):
    """adminops 安全领域异常基类。"""


class ReportRateLimited(SafetyError):
    """当日举报次数超限（429 RATE_LIMITED，带 ``Retry-After``）。"""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(
            "RATE_LIMITED",
            f"今日举报次数已达上限（{REPORT_DAILY_LIMIT} 次）",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=retry_after,
        )


class SelfBlock(SafetyError):
    """拉黑自己（400 SELF_REQUEST）。"""

    def __init__(self) -> None:
        super().__init__(
            "SELF_REQUEST",
            "不能拉黑自己",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class BlockTargetNotFound(SafetyError):
    """目标用户不存在或已被禁用（404 USER_NOT_FOUND，不暴露禁用）。"""

    def __init__(self) -> None:
        super().__init__(
            "USER_NOT_FOUND",
            "用户不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )


def _now(at: datetime | None = None) -> datetime:
    if at is None:
        return timezone.now()
    if timezone.is_naive(at):
        return timezone.make_aware(at, timezone.get_current_timezone())
    return at


def _day_start(now: datetime) -> datetime:
    """按项目时区（Asia/Shanghai）取当天 00:00（与 connections 日限流一致）。"""
    local = timezone.localtime(now)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _seconds_until_next_day(now: datetime) -> int:
    """``Retry-After``：距次日 00:00 的整秒数（至少 1）。"""
    tomorrow = _day_start(now) + timedelta(days=1)
    return max(1, int((tomorrow - now).total_seconds()))


def _reports_today(reporter: Any, now: datetime) -> int:
    return Report.objects.filter(
        reporter=reporter,
        created_at__gte=_day_start(now),
    ).count()


def create_report(
    reporter: Any,
    *,
    target_type: str,
    target_id: int,
    reason: str,
    at: datetime | None = None,
) -> Report:
    """落一条举报；每举报人每日 10 次（429 + Retry-After）。"""
    now = _now(at)
    with transaction.atomic():
        # 锁本人行，避免并发下把日限频打穿；不锁窗口（举报不受时间窗限制）。
        lock_users([getattr(reporter, "pk", reporter)])
        if _reports_today(reporter, now) >= REPORT_DAILY_LIMIT:
            raise ReportRateLimited(_seconds_until_next_day(now))
        return Report.objects.create(
            reporter=reporter,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
        )


def list_blocks(blocker: Any) -> QuerySet[Block]:
    """本人拉黑列表，新拉黑的在前（分页在视图层）。"""
    return (
        Block.objects.filter(blocker=blocker)
        .select_related("blocked")
        .order_by("-created_at", "-id")
    )


def block_user(
    blocker: User,
    uid: str,
    *,
    request_id: str = "",
) -> bool:
    """拉黑 ``uid``（幂等）；返回是否新建，副作用只在新建时发生。"""
    target = User.objects.filter(uid=uid).first()
    if target is None:
        raise BlockTargetNotFound()
    if target.pk == blocker.pk:
        raise SelfBlock()
    if Block.objects.filter(blocker=blocker, blocked=target).exists():
        return False
    if target.status != User.Status.ACTIVE:
        raise BlockTargetNotFound()

    with transaction.atomic():
        lock_users([blocker.pk, target.pk])
        _, created = Block.objects.get_or_create(blocker=blocker, blocked=target)
        if not created:
            return False
        _close_open_requests(blocker, target, request_id=request_id)
    return True


def unblock_user(blocker: User, uid: str) -> int:
    """取消拉黑（幂等）：返回删除条数；不写审计（02 §9.2 无该事件）。"""
    with transaction.atomic():
        deleted, _ = Block.objects.filter(blocker=blocker, blocked__uid=uid).delete()
    return deleted


def _close_open_requests(blocker: User, blocked: User, *, request_id: str) -> int:
    """关闭双方全部在途请求：``CANCELLED/BLOCKED`` + 双方 SYSTEM 通知 + 审计。"""
    ids = list(
        ConnectionRequest.objects.filter(status__in=OPEN_STATUSES)
        .filter(
            Q(initiator_id=blocker.pk, target_id=blocked.pk)
            | Q(initiator_id=blocked.pk, target_id=blocker.pk),
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if not ids:
        return 0

    closed = 0
    for row in lock_requests(ids):
        if row.status not in OPEN_STATUSES:
            continue
        row.status = ConnectionRequest.Status.CANCELLED
        row.close_reason = ConnectionRequest.CloseReason.BLOCKED
        row.closed_by = blocker
        row.version += 1
        row.save(
            update_fields=[
                "status",
                "close_reason",
                "closed_by",
                "version",
                "updated_at",
            ]
        )

        payload: dict[str, Any] = {
            "connection_id": row.pk,
            "reason": ConnectionRequest.CloseReason.BLOCKED,
        }
        if row.room_id is not None:
            payload["room_code"] = row.room.code
        for party in (row.initiator, row.target):
            notify(party, Notification.Type.SYSTEM, payload)

        write_audit(
            BLOCK_AUDIT_ACTION,
            "connection",
            row.pk,
            actor=blocker,
            meta={
                "blocker_id": blocker.pk,
                "blocked_id": blocked.pk,
                "reason": ConnectionRequest.CloseReason.BLOCKED,
            },
            request_id=request_id,
        )
        closed += 1
    return closed
