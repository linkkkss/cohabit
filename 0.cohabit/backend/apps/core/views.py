"""系统级接口：健康检查、管理看板与时间窗状态（docs/04 §1.8、§3.13、§4.7）。"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from django.db import connections
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.adminops.models import TimeWindow

API_VERSION = "0.1.0"
OPEN_ROOM_STATUSES = ("RECRUITING", "FULL", "LOCKED")
OPEN_CONNECTION_STATUSES = ("PENDING", "CONTACT_SHARED", "CONFIRMING")

WINDOW_STATUS_OPEN = "OPEN"
WINDOW_STATUS_UPCOMING = "UPCOMING"
WINDOW_STATUS_CLOSED = "CLOSED"
_SECONDS_PER_DAY = 24 * 60 * 60


def _database_healthy() -> bool:
    """执行最小 ``SELECT 1``；只探测数据库，不触碰缓存/外部依赖。"""
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - 探针必须把任何驱动错误映射为 degraded
        return False
    return True


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness/readiness 探针：数据库可用 200，否则 503 degraded。"""
    healthy = _database_healthy()
    payload = {
        "status": "ok" if healthy else "degraded",
        "version": API_VERSION,
        "db": "ok" if healthy else "error",
        "time": timezone.now().isoformat(),
    }
    if not healthy:
        return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_stats(request):
    """管理看板计数（docs/04 §4.7）：仅 staff 可访问。"""
    if not getattr(request.user, "is_staff", False):
        return Response(
            {
                "code": "FORBIDDEN",
                "message": "仅管理员可访问。",
                "detail": None,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    from apps.accounts.models import User
    from apps.adminops.models import Block, Report
    from apps.connections.models import ConnectionRequest
    from apps.rooms.models import Room

    users = User.objects.all()
    rooms = Room.objects.all()
    connections = ConnectionRequest.objects.all()
    reports = Report.objects.all()

    payload = {
        "users": {
            "total": users.count(),
            "active": users.filter(status="ACTIVE", is_active=True).count(),
            "disabled": users.filter(status="DISABLED").count(),
        },
        "rooms": {
            "total": rooms.count(),
            "active": rooms.filter(status__in=OPEN_ROOM_STATUSES).count(),
            "dissolved": rooms.filter(status="DISSOLVED").count(),
        },
        "connections": {
            "total": connections.count(),
            "open": connections.filter(status__in=OPEN_CONNECTION_STATUSES).count(),
        },
        "reports": {
            "total": reports.count(),
            "open": reports.filter(status="OPEN").count(),
        },
        "blocks": {"total": Block.objects.count()},
        "generated_at": timezone.now().isoformat(),
    }
    return Response(payload)


def _local_iso(value: datetime | None) -> str | None:
    """序列化为服务器本地时区（``TIME_ZONE``）的 ISO 8601（docs/04 §4.7）。"""
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value).isoformat()


def _days_until(target: datetime, now: datetime) -> int:
    """剩余时间向上取整到天：整 7 天→7，多 1 秒→8（docs/04 §3.13）。"""
    return math.ceil((target - now).total_seconds() / _SECONDS_PER_DAY)


def _timewindow_payload(college: str, now: datetime) -> dict[str, Any]:
    """组装时间窗状态响应；无记录、无学院或已结束一律 CLOSED。"""
    payload: dict[str, Any] = {
        "college": college,
        "status": WINDOW_STATUS_CLOSED,
        "is_open": False,
        "start_at": None,
        "end_at": None,
        "days_until_start": None,
        "days_until_end": None,
        "server_time": _local_iso(now),
    }

    window = TimeWindow.objects.filter(college=college).first() if college else None
    if window is None:
        return payload

    payload["start_at"] = _local_iso(window.start_at)
    payload["end_at"] = _local_iso(window.end_at)
    if now < window.start_at:
        payload["status"] = WINDOW_STATUS_UPCOMING
        payload["days_until_start"] = _days_until(window.start_at, now)
    elif now < window.end_at:
        payload["status"] = WINDOW_STATUS_OPEN
        payload["is_open"] = True
        payload["days_until_start"] = 0
        payload["days_until_end"] = _days_until(window.end_at, now)
    return payload


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def timewindow_status(request):
    """只读时间窗状态（docs/04 §1.8、§3.13）：供页面横幅与 CTA 禁用态。"""
    college = str(getattr(request.user, "college", "") or "")
    return Response(_timewindow_payload(college, timezone.now()))
