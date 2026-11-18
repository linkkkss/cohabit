"""rooms API（docs/04 §4.3）。

路由刻意不提供 ``POST /api/rooms``，也没有公开的 join 接口：建寝只发生在
connections 的 ``INVITE`` 二次确认里，入寝只发生在邀请/申请确认里。

路由顺序（同 docs/04 §4.3 的要求）：``mine`` → 9 位 ``code`` → 数字 ``id``。
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.exceptions import ApiError, accounts_exception_handler
from apps.accounts.permissions import IsStudentOrReadOnly
from apps.connections.models import OPEN_STATUSES, ConnectionRequest

from . import services, transfer_services
from .exceptions import CapacityImmutable, NotOwner, RoomNotFound
from .models import Room, RoomMember, RoomTransfer
from .serializers import (
    RoomUpdateSerializer,
    TransferCreateSerializer,
    pending_application_payload,
    public_room_payload,
    room_detail,
    room_summary,
    transfer_summary,
)
from .services import normalize_capacity
from .utils import TAGS_MAX


class RoomAPIView(APIView):
    """rooms 视图基类：统一鉴权与错误信封。"""

    permission_classes = [IsAuthenticated, IsStudentOrReadOnly]

    def get_exception_handler(self):  # noqa: ANN201 - DRF 约定
        return accounts_exception_handler


class PublicRoomAPIView(APIView):
    """公开寝室页：免登录、只读、无 uid/联系方式。"""

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    def get_exception_handler(self):  # noqa: ANN201
        return accounts_exception_handler


# --------------------------------------------------------------------------- #
# 广场 / 我的寝室 / 详情
# --------------------------------------------------------------------------- #
class RoomSquareView(RoomAPIView):
    """GET /api/rooms：同学院同性别、仅招募中且有空位的寝室。"""

    def get(self, request):  # noqa: ANN201
        params = request.query_params
        major = (params.get("major") or "").strip() or None
        capacity = None
        raw_capacity = (params.get("capacity") or "").strip()
        if raw_capacity:
            try:
                capacity = normalize_capacity(int(raw_capacity))
            except (TypeError, ValueError):
                raise ApiError(
                    "CAPACITY_INVALID",
                    "容量只能是 2/4/6",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"capacity": raw_capacity},
                ) from None
        tags = _parse_tags(params)[:TAGS_MAX]

        queryset = services.square_rooms(
            request.user,
            major=major,
            capacity=capacity,
            tags=tags,
        )
        paginator = _paginator()
        page = paginator.paginate_queryset(queryset, request, view=self)
        viewer_active = RoomMember.objects.filter(
            user_id=request.user.pk,
            status=RoomMember.Status.ACTIVE,
        ).exists()
        pending_room_ids = set(
            ConnectionRequest.objects.filter(
                initiator_id=request.user.pk,
                status__in=OPEN_STATUSES,
                room__isnull=False,
            ).values_list("room_id", flat=True)
        )
        items: list[dict[str, Any]] = []
        for room in page:
            payload = room_summary(room, request.user)
            payload["can_apply"] = _square_can_apply(
                room,
                request.user,
                viewer_active=viewer_active,
                pending_room_ids=pending_room_ids,
            )
            items.append(payload)
        return paginator.get_paginated_response(items)


def _square_can_apply(
    room: Room,
    viewer: Any,
    *,
    viewer_active: bool,
    pending_room_ids: set[int],
) -> bool:
    if viewer_active:
        return False
    if room.pk in pending_room_ids:
        return False
    if room.status != Room.Status.RECRUITING or room.member_count >= room.capacity:
        return False
    return room.gender == viewer.gender and room.college == viewer.college


class RoomMineView(RoomAPIView):
    """GET /api/rooms/mine：当前寝室 + 待处理申请 + 待处理转让。

    没有 ACTIVE 寝室时，若存在最近一间终态（ARCHIVED/DISSOLVED）房间的历史
    成员记录，则返回该房间的只读 RoomDetail（docs/02 §4.8/§4.9），否则空壳。
    """

    def get(self, request):  # noqa: ANN201
        viewer = request.user
        membership = services.room_memberships(viewer)
        if membership is None:
            historical = services.latest_terminal_membership(viewer)
            if historical is None:
                return Response(
                    {
                        "room": None,
                        "pending_applications": [],
                        "pending_transfer": None,
                    }
                )
            return Response(
                {
                    "room": room_detail(
                        historical.room,
                        viewer,
                        membership=historical,
                    ),
                    "pending_applications": [],
                    "pending_transfer": None,
                }
            )
        room = membership.room
        transfer = transfer_services.pending_transfer_for(room)
        payload = room_detail(
            room,
            viewer,
            membership=membership,
            pending_transfer=transfer,
        )

        applications: list[dict[str, Any]] = []
        if membership.role == RoomMember.Role.OWNER:
            rows = (
                ConnectionRequest.objects.select_related("initiator", "room")
                .filter(room_id=room.pk, status__in=OPEN_STATUSES)
                .filter(Q(type=ConnectionRequest.Type.APPLY) | Q(initiator_id=viewer.pk))
                .order_by("-created_at", "-id")[:50]
            )
            applications = [pending_application_payload(row) for row in rows]
        return Response(
            {
                "room": payload,
                "pending_applications": applications,
                "pending_transfer": (
                    transfer_summary(transfer) if transfer is not None else None
                ),
            }
        )


class RoomDetailView(RoomAPIView):
    """GET /api/rooms/:code 与 PATCH /api/rooms/:id。

    ``GET`` 只接受 9 位 code；内部主键路由只用于 PATCH，避免与
    ``docs/04-API契约.md`` §4.3 的 ``str:code`` / ``int:id`` 约束不一致。
    """

    def get(self, request, code: Any = None, room_id: Any = None):  # noqa: ANN201
        if code is None:
            raise RoomNotFound()
        room, membership = services.get_room_for_viewer(
            request.user,
            code=code,
        )
        transfer = transfer_services.pending_transfer_for(room)
        return Response(
            room_detail(
                room,
                request.user,
                membership=membership,
                pending_transfer=transfer,
            )
        )

    def patch(self, request, room_id: Any = None, code: Any = None):  # noqa: ANN201
        if room_id is None:  # 9 位 code 路由只读
            raise RoomNotFound()
        data = request.data if isinstance(request.data, dict) else {}
        if "capacity" in data:
            raise CapacityImmutable()
        serializer = RoomUpdateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        room = services.update_room(
            request.user,
            room_id,
            title=serializer.validated_data.get("title"),
            tags=serializer.validated_data.get("tags"),
            request_id=_request_id(request),
        )
        membership = RoomMember.objects.filter(
            room_id=room.pk,
            user_id=request.user.pk,
            status=RoomMember.Status.ACTIVE,
        ).first()
        transfer = transfer_services.pending_transfer_for(room)
        return Response(
            room_detail(
                room,
                request.user,
                membership=membership,
                pending_transfer=transfer,
            )
        )


# --------------------------------------------------------------------------- #
# 生命周期动作
# --------------------------------------------------------------------------- #
class RoomLockView(RoomAPIView):
    def post(self, request, room_id: Any):  # noqa: ANN201
        room = services.lock_room(request.user, room_id, request_id=_request_id(request))
        return Response(_action_detail(room, request.user))


class RoomUnlockView(RoomAPIView):
    def post(self, request, room_id: Any):  # noqa: ANN201
        room = services.unlock_room(request.user, room_id, request_id=_request_id(request))
        return Response(_action_detail(room, request.user))


class RoomDissolveView(RoomAPIView):
    def post(self, request, room_id: Any):  # noqa: ANN201
        room = services.dissolve_room(
            request.user,
            room_id,
            request_id=_request_id(request),
        )
        return Response(_action_detail(room, request.user))


class RoomLeaveView(RoomAPIView):
    def post(self, request, room_id: Any):  # noqa: ANN201
        services.leave_room(request.user, room_id, request_id=_request_id(request))
        return Response(_action_detail(_reload_room(room_id), request.user))


class RoomMemberView(RoomAPIView):
    """DELETE /api/rooms/:id/members/:uid：房主移除成员。"""

    def delete(self, request, room_id: Any, uid: str):  # noqa: ANN201
        target = _find_user_by_uid(uid)
        if target is None:
            raise NotOwner(detail={"reason": "USER_NOT_FOUND"})
        services.remove_member(
            request.user,
            room_id,
            target.pk,
            request_id=_request_id(request),
        )
        return Response(_action_detail(_reload_room(room_id), request.user))


# --------------------------------------------------------------------------- #
# 房主转让
# --------------------------------------------------------------------------- #
class RoomTransferCreateView(RoomAPIView):
    def post(self, request, room_id: Any):  # noqa: ANN201
        serializer = TransferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = transfer_services.create_transfer(
            request.user,
            room_id,
            serializer.validated_data["to_uid"],
            request_id=_request_id(request),
        )
        return Response(
            transfer_summary(_reload_transfer(transfer.pk)),
            status=status.HTTP_201_CREATED,
        )


class TransferActionView(RoomAPIView):
    """POST /api/room-transfers/:id/{accept,decline,cancel}。"""

    action_name = "accept"

    def post(self, request, transfer_id: Any):  # noqa: ANN201
        handler = {
            "accept": transfer_services.accept_transfer,
            "decline": transfer_services.decline_transfer,
            "cancel": transfer_services.cancel_transfer,
        }[self.action_name]
        transfer = handler(
            request.user,
            transfer_id,
            request_id=_request_id(request),
        )
        return Response(transfer_summary(_reload_transfer(transfer.pk)))


class TransferAcceptView(TransferActionView):
    action_name = "accept"


class TransferDeclineView(TransferActionView):
    action_name = "decline"


class TransferCancelView(TransferActionView):
    action_name = "cancel"


# --------------------------------------------------------------------------- #
# 公开寝室页
# --------------------------------------------------------------------------- #
class PublicRoomView(PublicRoomAPIView):
    def get(self, request, code: str):  # noqa: ANN201
        return Response(public_room_payload(services.public_room(code)))


# --------------------------------------------------------------------------- #
# 内部小工具
# --------------------------------------------------------------------------- #
def _paginator():  # noqa: ANN201
    from config.api import StandardPagination

    return StandardPagination()


def _parse_tags(params: Any) -> list[str]:
    tags: list[str] = []
    for raw in params.getlist("tags"):
        for piece in str(raw).split(","):
            text = piece.strip()
            if text and text not in tags:
                tags.append(text)
    return tags


def _request_id(request: Any) -> str:
    value = request.headers.get("X-Request-Id") or request.META.get("HTTP_X_REQUEST_ID")
    return str(value or "")[:64]


def _find_user_by_uid(uid: Any):  # noqa: ANN201
    from apps.accounts.models import User

    text = str(uid or "").strip()
    if not text:
        return None
    return User.objects.filter(uid=text).first()


def _reload_room(room_id: Any) -> Room:
    room = (
        Room.objects.select_related("owner")
        .prefetch_related("members__user")
        .filter(pk=room_id)
        .first()
    )
    if room is None:
        raise RoomNotFound()
    return room


def _reload_transfer(transfer_id: Any) -> RoomTransfer:
    transfer = (
        RoomTransfer.objects.select_related("from_owner", "to_member", "room")
        .filter(pk=transfer_id)
        .first()
    )
    if transfer is None:  # pragma: no cover - 防御性
        raise RoomNotFound()
    return transfer


def _action_detail(room: Room, viewer: Any) -> dict[str, Any]:
    membership = RoomMember.objects.filter(
        room_id=room.pk,
        user_id=getattr(viewer, "pk", None),
    ).first()
    if membership is not None and membership.status != RoomMember.Status.ACTIVE:
        membership = None
    transfer = transfer_services.pending_transfer_for(room)
    return room_detail(room, viewer, membership=membership, pending_transfer=transfer)
