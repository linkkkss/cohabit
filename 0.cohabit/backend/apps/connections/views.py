"""connections API（docs/04 §4.4）。

* ``POST /api/connections`` 创建邀请/申请（组合规则由服务层判定）；
* ``GET /api/connections`` 参与者列表，``role``/``box`` 兼容 ``inbox|sent``；
* ``GET /api/connections/:id`` 详情，contact 仅在解锁状态返回；
* ``accept/decline/cancel/confirm`` 四个动作全部 200 + ConnectionDetail；
* 非参与者或不存在的请求统一 404 ``CONNECTION_NOT_FOUND``。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.exceptions import accounts_exception_handler
from apps.accounts.permissions import IsStudentOrReadOnly
from apps.rooms.serializers import room_summary
from config.api import StandardPagination

from . import services
from .models import ConnectionRequest
from .serializers import (
    ConnectionCreateSerializer,
    connection_detail,
    connection_summary,
    parse_statuses,
)

_REQUEST_ID_MAX_LENGTH = 64


class ConnectionAPIView(APIView):
    """connections 视图基类：统一鉴权与错误信封。"""

    permission_classes = [IsAuthenticated, IsStudentOrReadOnly]

    def get_exception_handler(self) -> Any:
        return accounts_exception_handler


def _request_id(request: Request) -> str:
    raw = request.headers.get("X-Request-Id", "") or ""
    return str(raw)[:_REQUEST_ID_MAX_LENGTH]


def _reload(request: Request, connection_id: int) -> ConnectionRequest:
    return services.get_request(request.user, connection_id)


class ConnectionCollectionView(ConnectionAPIView):
    """``/api/connections``：GET 列表，POST 创建 INVITE/APPLY。"""

    def get(self, request: Request) -> Response:
        params = request.query_params
        box = params.get("box") or params.get("role") or "inbox"
        statuses = parse_statuses(
            list(params.getlist("status")) + list(params.getlist("status[]"))
        )
        queryset = services.list_requests(request.user, box=box, statuses=statuses)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = [connection_summary(row, request.user) for row in page]
        return paginator.get_paginated_response(data)

    def post(self, request: Request) -> Response:
        serializer = ConnectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        row = services.create_request(
            request.user,
            type=data.get("type"),
            target_uid=data.get("target_uid"),
            room_id=data.get("room_id"),
            capacity_pref=data.get("capacity_pref"),
            message=data.get("message") or "",
            request_id=_request_id(request),
        )
        detail = connection_detail(_reload(request, row.pk), request.user)
        return Response(detail, status=status.HTTP_201_CREATED)


class ConnectionDetailView(ConnectionAPIView):
    """``GET /api/connections/:id``：参与者可见，否则 404。"""

    def get(self, request: Request, connection_id: int) -> Response:
        row = _reload(request, connection_id)
        return Response(connection_detail(row, request.user))


class ConnectionAcceptView(ConnectionAPIView):
    """``POST /api/connections/:id/accept``：目标接受，返回 contact。"""

    def post(self, request: Request, connection_id: int) -> Response:
        row = services.accept_request(
            request.user,
            connection_id,
            request_id=_request_id(request),
        )
        return Response(
            connection_detail(_reload(request, row.pk), request.user),
            status=status.HTTP_200_OK,
        )


class ConnectionDeclineView(ConnectionAPIView):
    """``POST /api/connections/:id/decline``：目标拒绝。"""

    def post(self, request: Request, connection_id: int) -> Response:
        row = services.decline_request(
            request.user,
            connection_id,
            request_id=_request_id(request),
        )
        return Response(
            connection_detail(_reload(request, row.pk), request.user),
            status=status.HTTP_200_OK,
        )


class ConnectionCancelView(ConnectionAPIView):
    """``POST /api/connections/:id/cancel``：撤回 / 结束了解。"""

    def post(self, request: Request, connection_id: int) -> Response:
        row = services.cancel_request(
            request.user,
            connection_id,
            request_id=_request_id(request),
        )
        return Response(
            connection_detail(_reload(request, row.pk), request.user),
            status=status.HTTP_200_OK,
        )


class ConnectionConfirmView(ConnectionAPIView):
    """``POST /api/connections/:id/confirm``：两步确认（第一步 CONFIRMING）。"""

    def post(self, request: Request, connection_id: int) -> Response:
        _, row, room = services.confirm_request(
            request.user,
            connection_id,
            request_id=_request_id(request),
        )
        payload = connection_detail(_reload(request, row.pk), request.user)
        if room is not None:
            payload["room"] = room_summary(room, request.user)
        return Response(payload, status=status.HTTP_200_OK)
