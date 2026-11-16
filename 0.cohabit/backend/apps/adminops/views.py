"""adminops 安全 API：举报与拉黑（docs/04 §4.6）。

学生端只暴露四个动作：提交举报、查看/新增/取消拉黑；全部要求登录，
错误信封复用 ``accounts_exception_handler``（与 connections/notifications 一致）。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.exceptions import accounts_exception_handler
from config.api import StandardPagination

from . import services
from .serializers import (
    BlockUidSerializer,
    ReportCreateSerializer,
    block_payload,
    report_payload,
)

_REQUEST_ID_MAX_LENGTH = 64


def _request_id(request: Request) -> str:
    raw = request.headers.get("X-Request-Id", "") or ""
    return str(raw)[:_REQUEST_ID_MAX_LENGTH]


class SafetyAPIView(APIView):
    """安全接口基类：登录必需 + 统一错误信封。"""

    permission_classes = [IsAuthenticated]

    def get_exception_handler(self) -> Any:
        return accounts_exception_handler


class ReportCreateView(SafetyAPIView):
    """``POST /api/reports``：只落 Report，201 返回举报本身。"""

    def post(self, request: Request) -> Response:
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        report = services.create_report(
            request.user,
            target_type=data["target_type"],
            target_id=data["target_id"],
            reason=data["reason"],
        )
        return Response(report_payload(report), status=status.HTTP_201_CREATED)


class BlockCollectionView(SafetyAPIView):
    """``GET /api/blocks`` 本人黑名单（分页）/ ``POST /api/blocks`` 拉黑（204）。"""

    def get(self, request: Request) -> Response:
        queryset = services.list_blocks(request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([block_payload(row) for row in page])

    def post(self, request: Request) -> Response:
        serializer = BlockUidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.block_user(
            request.user,
            serializer.validated_data["uid"],
            request_id=_request_id(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockDetailView(SafetyAPIView):
    """``DELETE /api/blocks/:uid``：取消拉黑，幂等 204。"""

    def delete(self, request: Request, uid: str) -> Response:
        serializer = BlockUidSerializer(data={"uid": uid})
        serializer.is_valid(raise_exception=True)
        services.unblock_user(request.user, serializer.validated_data["uid"])
        return Response(status=status.HTTP_204_NO_CONTENT)
