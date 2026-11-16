"""adminops 安全接口的入参校验与出参构造（docs/04 §4.6）。

举报与拉黑都在学生端：只做字段校验与响应拼装，业务规则放 ``services``。
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import UID_LENGTH
from apps.accounts.serializers import avatar_key_for
from apps.rooms.utils import isoformat

from .models import Block, Report

REASON_MAX_LENGTH = 200
UID_PATTERN = rf"^\d{{{UID_LENGTH}}}$"


class ReportCreateSerializer(serializers.Serializer):
    """``POST /api/reports`` 入参（docs/04 §4.6、docs/openapi ReportCreate）。"""

    target_type = serializers.ChoiceField(
        choices=Report.TargetType.choices,
        error_messages={
            "required": "缺少 target_type",
            "invalid_choice": "target_type 只能是 USER/ROOM/CONNECTION",
            "null": "target_type 不能为空",
        },
    )
    target_id = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": "缺少 target_id",
            "invalid": "target_id 必须是正整数",
            "min_value": "target_id 必须是正整数",
            "null": "target_id 不能为空",
        },
    )
    reason = serializers.CharField(
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "required": "举报理由不能为空",
            "blank": "举报理由不能为空",
            "max_length": f"举报理由最多 {REASON_MAX_LENGTH} 字",
            "null": "举报理由不能为空",
        },
    )


class BlockUidSerializer(serializers.Serializer):
    """``POST /api/blocks {uid}`` 与 ``DELETE /api/blocks/:uid`` 的 uid 校验。"""

    uid = serializers.RegexField(
        UID_PATTERN,
        error_messages={
            "required": "缺少 uid",
            "blank": f"uid 必须是 {UID_LENGTH} 位数字",
            "invalid": f"uid 必须是 {UID_LENGTH} 位数字",
            "null": f"uid 必须是 {UID_LENGTH} 位数字",
        },
    )


def report_payload(report: Report) -> dict[str, Any]:
    """举报响应体（docs/openapi ``Report``）：不回传举报人信息。"""
    return {
        "id": report.pk,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "reason": report.reason,
        "status": report.status,
        "handled_by": report.handled_by_id,
        "created_at": isoformat(report.created_at),
    }


def block_payload(block: Block) -> dict[str, Any]:
    """黑名单条目（docs/openapi ``Block``）：只有公开摘要字段。"""
    blocked = block.blocked
    return {
        "uid": blocked.uid,
        "nickname": blocked.nickname,
        "avatar_key": avatar_key_for(blocked.uid),
        "created_at": isoformat(block.created_at),
    }
