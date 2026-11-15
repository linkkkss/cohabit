"""审计写入 helper（docs/02 §9、docs/03 §1.8.3）。

约定：

* 只增不改：本模块只提供写入，没有 update/delete API；
* **必须与业务同事务**：调用方把 ``write_audit`` 放在自己的
  ``transaction.atomic()`` 内、不要用 ``on_commit``（docs/02 §14.3）；
* ``actor=None`` 表示系统/cron；
* ``meta`` 只允许 id、状态、原因、from/to、计数等非敏感字段，写前过隐私护栏。
"""

from __future__ import annotations

import re
from typing import Any

from apps.adminops.models import AuditLog

from .privacy import assert_public_payload

# docs/02 §9.1 用 connection/room/room_member/... 描述目标；模型（docs/03
# §1.8.3）使用大写枚举。这里同时接受两套写法，统一落到模型枚举。
_TARGET_TYPE_ALIASES: dict[str, str] = {
    "connection": "CONNECTION",
    "room": "ROOM",
    "room_member": "ROOM",
    "transfer": "TRANSFER",
    "time_window": "WINDOW",
    "window": "WINDOW",
    "user": "USER",
    "report": "REPORT",
    "invite_code": "INVITE",
    "invite": "INVITE",
    "notification": "NOTIFICATION",
}

_ACTION_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ACTION_MAX_LENGTH = 50
_TARGET_TYPE_MAX_LENGTH = 20
_REQUEST_ID_MAX_LENGTH = 64


def normalize_target_type(target_type: Any) -> str:
    """把 docs/02 的小写目标类型或模型枚举规范化为 ``AuditLog.TargetType`` 值。"""
    raw = str(getattr(target_type, "value", target_type) or "").strip()
    if not raw:
        raise ValueError("target_type 不能为空")
    if raw.upper() in AuditLog.TargetType.values:
        return raw.upper()
    alias = _TARGET_TYPE_ALIASES.get(raw.lower())
    if alias is not None:
        return alias
    allowed = "/".join(AuditLog.TargetType.values)
    raise ValueError(f"未知的 target_type：{raw!r}（可用：{allowed}）")


def normalize_action(action: Any) -> str:
    """规范化审计事件名：大写后校验 ``[A-Z][A-Z0-9_]*``。"""
    raw = str(getattr(action, "value", action) or "").strip().upper()
    if not raw:
        raise ValueError("action 不能为空")
    if len(raw) > _ACTION_MAX_LENGTH:
        raise ValueError(f"action 超过 {_ACTION_MAX_LENGTH} 字符：{raw!r}")
    if not _ACTION_PATTERN.match(raw):
        raise ValueError(f"action 必须是 UPPER_SNAKE_CASE：{raw!r}")
    return raw


def _resolve_pk(value: Any) -> int | None:
    """接受模型实例/主键/``None``，返回可写入外键列的主键。"""
    if value is None:
        return None
    pk = getattr(value, "pk", value)
    if pk is None:
        return None
    try:
        return int(pk)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"无法解析主键：{value!r}") from exc


def write_audit(
    action: Any,
    target_type: Any,
    target_id: Any = None,
    *,
    actor: Any = None,
    meta: dict[str, Any] | None = None,
    request_id: Any = "",
) -> AuditLog:
    """写入一条审计日志并返回实例；调用方负责事务边界。

    :param action: §9.2 的事件名（大小写不敏感，统一存大写）。
    :param target_type: 目标类型，接受模型枚举或 docs/02 的小写写法。
    :param target_id: 目标主键；``user`` 目标传 user_id。
    :param actor: 操作者实例/主键；``None`` 表示系统或 cron。
    :param meta: 非敏感元数据，禁止联系方式/邮箱/真名/token。
    :param request_id: 同一 HTTP 请求共享的追踪 id（cron 用批次 id）。
    """

    normalized_action = normalize_action(action)
    normalized_target = normalize_target_type(target_type)
    if len(normalized_target) > _TARGET_TYPE_MAX_LENGTH:
        raise ValueError(f"target_type 超过 {_TARGET_TYPE_MAX_LENGTH} 字符")
    if meta is not None and not isinstance(meta, dict):
        raise ValueError("meta 必须是 JSON 对象")
    assert_public_payload(meta, where="AuditLog.meta")

    return AuditLog.objects.create(
        actor_id=_resolve_pk(actor),
        action=normalized_action,
        target_type=normalized_target,
        target_id=_resolve_pk(target_id),
        meta=dict(meta or {}),
        request_id=str(request_id or "")[:_REQUEST_ID_MAX_LENGTH],
    )
