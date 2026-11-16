"""系统级接口：健康检查与管理看板（docs/04 §3.13、§4.7）。"""

from __future__ import annotations

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

API_VERSION = "0.1.0"
OPEN_ROOM_STATUSES = ("RECRUITING", "FULL", "LOCKED")
OPEN_CONNECTION_STATUSES = ("PENDING", "CONTACT_SHARED", "CONFIRMING")


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
