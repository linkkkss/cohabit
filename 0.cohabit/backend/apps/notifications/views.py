"""通知 API（docs/04 §4.5）。

* 全部端点仅登录用户可访问；只能读写本人通知；
* 列表按 ``created_at DESC, id DESC``，分页默认 20、最大 50；
* 标记已读幂等：重复调用返回 200，不改变首次 ``read_at``；
* 通知不存在或非本人统一返回 ``404 NOTIFICATION_NOT_FOUND``，不泄露存在性。
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.exceptions import accounts_exception_handler
from config.api import StandardPagination

from .exceptions import NotificationNotFound
from .models import Notification
from .serializers import NotificationSerializer

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class NotificationAPIView(APIView):
    """通知端点基类：认证 + 与 accounts 一致的错误信封（AUTH_REQUIRED 等）。"""

    permission_classes = [IsAuthenticated]

    def get_exception_handler(self) -> Any:
        return accounts_exception_handler


class NotificationListView(NotificationAPIView):
    """``GET /api/notifications``：本人通知分页列表，支持 ``unread=true``。"""

    def get(self, request: Request) -> Response:
        queryset = Notification.objects.filter(user=request.user)
        unread = (request.query_params.get("unread") or "").strip().lower()
        if unread in _TRUTHY:
            queryset = queryset.filter(read_at__isnull=True)
        queryset = queryset.order_by("-created_at", "-id")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NotificationUnreadCountView(NotificationAPIView):
    """``GET /api/notifications/unread-count``：未读数（前端 20s 轮询）。"""

    def get(self, request: Request) -> Response:
        count = Notification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).count()
        return Response({"count": count})


class NotificationReadView(NotificationAPIView):
    """``POST /api/notifications/:id/read``：标记单条已读（幂等）。"""

    def post(self, request: Request, pk: int) -> Response:
        notification = Notification.objects.filter(user=request.user, pk=pk).first()
        if notification is None:
            raise NotificationNotFound()
        if notification.read_at is None:
            now = timezone.now()
            # 条件更新：并发重复点击只写入第一次的 read_at。
            Notification.objects.filter(pk=notification.pk, read_at__isnull=True).update(
                read_at=now
            )
            notification.read_at = now
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(NotificationAPIView):
    """``POST /api/notifications/read-all``：全部已读，返回本次更新条数。"""

    def post(self, request: Request) -> Response:
        updated = Notification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())
        return Response({"updated": updated})
