"""connections 序列化：请求摘要/详情、contact 可见性、actions 与入参校验。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rest_framework import serializers

from apps.accounts.models import ContactInfo
from apps.accounts.serializers import UserSummarySerializer
from apps.rooms.serializers import room_summary
from apps.rooms.utils import isoformat

from .models import OPEN_STATUSES, ConnectionRequest

# contact 只在解锁状态可见（docs/02 §3.8、§12 X-10/X-11）。
CONTACT_STATUSES = (
    ConnectionRequest.Status.CONTACT_SHARED,
    ConnectionRequest.Status.CONFIRMING,
    ConnectionRequest.Status.CONFIRMED,
)

MESSAGE_MAX_LENGTH = 200


def user_summary(user: Any) -> dict[str, Any] | None:
    if user is None:
        return None
    return UserSummarySerializer(user).data


def _dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return isoformat(value)


def _own_confirm_at(row: ConnectionRequest, viewer: Any) -> datetime | None:
    if viewer.pk == row.initiator_id:
        return row.initiator_confirm_at
    return row.target_confirm_at


def pre_approved(row: ConnectionRequest) -> bool:
    """发起人是否已在 ``PENDING`` 阶段先行确认（docs/02 §3.5.5）。"""
    return (
        row.status == ConnectionRequest.Status.PENDING
        and row.initiator_confirm_at is not None
    )


def contact_visible(row: ConnectionRequest, now: datetime | None = None) -> bool:
    """按状态判定 contact 是否可见；在途但已过期按“已过期”处理（X-10）。"""
    if row.status not in CONTACT_STATUSES:
        return False
    if row.status in OPEN_STATUSES:
        from django.utils import timezone

        moment = now or timezone.now()
        if row.expires_at is not None and row.expires_at <= moment:
            return False
    return True


def contact_payload(
    row: ConnectionRequest,
    viewer: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    """对方联系方式；不可见或对方全部关闭时返回 ``{}``（X-54）。"""
    if not contact_visible(row, now):
        return {}
    other_id = row.target_id if viewer.pk == row.initiator_id else row.initiator_id
    info = ContactInfo.objects.filter(user_id=other_id).first()
    if info is None:
        return {}
    payload: dict[str, Any] = {}
    if info.show_qq and info.qq:
        payload["qq"] = info.qq
    if info.show_wechat and info.wechat:
        payload["wechat"] = info.wechat
    if info.show_phone and info.phone:
        payload["phone"] = info.phone
    if not payload:
        return {}
    payload["unlocked"] = True
    return payload


def actions_for(row: ConnectionRequest, viewer: Any) -> dict[str, bool]:
    """docs/04 §5.1 的动作矩阵。"""
    is_initiator = viewer.pk == row.initiator_id
    is_target = viewer.pk == row.target_id
    status = row.status
    confirming_open = status in (
        ConnectionRequest.Status.CONTACT_SHARED,
        ConnectionRequest.Status.CONFIRMING,
    )
    return {
        "can_accept": is_target and status == ConnectionRequest.Status.PENDING,
        "can_decline": is_target and status == ConnectionRequest.Status.PENDING,
        "can_cancel": (
            status == ConnectionRequest.Status.PENDING and is_initiator
        )
        or confirming_open,
        "can_confirm": confirming_open
        and _own_confirm_at(row, viewer) is None,
        "can_view_contact": contact_visible(row),
        # 发起人先确认：对方不同意也能随时撤回，所以只开放给 PENDING 的发起人。
        "can_pre_approve": is_initiator
        and status == ConnectionRequest.Status.PENDING
        and row.initiator_confirm_at is None,
    }


def connection_summary(
    row: ConnectionRequest,
    viewer: Any,
) -> dict[str, Any]:
    """ConnectionSummary（docs/04 §3.9）：列表不含 contact 与确认时间。"""
    direction = "sent" if viewer.pk == row.initiator_id else "inbox"
    return {
        "id": row.pk,
        "type": row.type,
        "status": row.status,
        "direction": direction,
        "initiator": user_summary(row.initiator),
        "target": user_summary(row.target),
        "room": room_summary(row.room, viewer) if row.room_id else None,
        "message": row.message,
        "contact_shared_at": _dt(row.contact_shared_at),
        "expires_at": _dt(row.expires_at),
        # 异步确认：对方最近活跃 + 发起人是否已经先确认（docs/04 §3.9）。
        "initiator_last_active_at": _dt(row.initiator.last_active_at),
        "target_last_active_at": _dt(row.target.last_active_at),
        "initiator_pre_approved": pre_approved(row),
        # 失败原因（DECLINED/TIMEOUT/ROOM_DISSOLVED/…），列表卡片也要能解释。
        "close_reason": row.close_reason or "",
        "actions": actions_for(row, viewer),
    }


def connection_detail(
    row: ConnectionRequest,
    viewer: Any,
) -> dict[str, Any]:
    """ConnectionDetail（docs/04 §3.10）：含 contact 与确认时间。"""
    payload = connection_summary(row, viewer)
    payload.update(
        {
            "initiator_confirm_at": _dt(row.initiator_confirm_at),
            "target_confirm_at": _dt(row.target_confirm_at),
            "closed_by": user_summary(row.closed_by) if row.closed_by_id else None,
            "close_reason": row.close_reason or "",
            "contact": contact_payload(row, viewer),
            "version": row.version,
        }
    )
    return payload


class ConnectionCreateSerializer(serializers.Serializer):
    """``POST /api/connections`` 入参（组合规则由服务层判定）。"""

    type = serializers.CharField(max_length=10)
    target_uid = serializers.RegexField(
        r"^[0-9]{10}$",
        error_messages={
            "invalid": "target_uid 必须是 10 位数字",
            "required": "请提供 target_uid",
            "blank": "请提供 target_uid",
        },
    )
    room_id = serializers.IntegerField(required=False, allow_null=True)
    capacity_pref = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MESSAGE_MAX_LENGTH,
        trim_whitespace=False,
        error_messages={
            "max_length": f"留言最长 {MESSAGE_MAX_LENGTH} 字",
        },
    )


def parse_statuses(values: list[str] | None) -> list[str]:
    """把 ``status`` 查询参数（可重复/逗号分隔）规范化；非法值抛 400。"""
    from apps.accounts.exceptions import ApiError

    allowed = set(ConnectionRequest.Status.values)
    result: list[str] = []
    for raw in values or []:
        for part in str(raw).split(","):
            text = part.strip().upper()
            if not text:
                continue
            if text not in allowed:
                raise ApiError(
                    "VALIDATION_ERROR",
                    "status 取值不合法",
                    status_code=400,
                    detail={"fields": {"status": [f"未知状态：{part.strip()}"]}},
                )
            if text not in result:
                result.append(text)
    return result
