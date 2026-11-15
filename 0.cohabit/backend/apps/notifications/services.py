"""通知写入服务（docs/02 §8、docs/03 §9）。

设计约束：

* **与业务同事务**：本模块不开启独立事务、也不使用 ``on_commit``；调用方把
  ``notify`` 放在自己的 ``transaction.atomic()`` 内，通知插入失败会让业务动作
  整体回滚（docs/02 §8.1、docs/06 S-11）；
* 一个接收者一行；批量动作由调用方逐个调用；
* ``payload`` 只放 id/枚举/计数/时间/昵称/房间号等非敏感字段，写前过
  :func:`apps.core.privacy.assert_public_payload`；
* ``title`` 由调用方按 docs/03 §9.2 传入；不传时按 type/reason 自动生成，
  超长统一截断到 60 字（模型上限）。
"""

from __future__ import annotations

from typing import Any

from apps.core.privacy import assert_public_payload

from .models import Notification

TITLE_MAX_LENGTH = 60

# docs/03 §9.2 标题模板。``SYSTEM`` 不在此表，按 §9.3 的 reason 映射。
TITLE_TEMPLATES: dict[str, str] = {
    Notification.Type.CONNECTION_RECEIVED: "{nickname} 想和你组寝",
    Notification.Type.CONTACT_SHARED: "可以交换联系方式了",
    Notification.Type.CONFIRM_PENDING: "{nickname} 已确认，等你确认",
    Notification.Type.CONFIRMED: "组寝成功：{room_code}",
    Notification.Type.DECLINED: "{nickname} 拒绝了请求",
    Notification.Type.MEMBER_JOINED: "{nickname} 加入了 {room_code}",
    Notification.Type.ROOM_FULL: "{room_code} 已满员",
    Notification.Type.MEMBER_LEFT: "{nickname} 退出了 {room_code}",
    Notification.Type.ROOM_LOCKED: "{room_code} 已锁定",
    Notification.Type.ROOM_DISSOLVED: "{room_code} 已解散",
    Notification.Type.ROOM_ARCHIVED: "{room_code} 已归档",
    Notification.Type.TRANSFER_RECEIVED: "{nickname} 想转让房主",
    Notification.Type.TRANSFER_ACCEPTED: "房主转让成功",
    Notification.Type.TRANSFER_DECLINED: "房主转让被拒绝",
    Notification.Type.TRANSFER_EXPIRED: "房主转让已过期",
    Notification.Type.TRANSFER_CANCELLED: "房主转让已取消",
    Notification.Type.WINDOW_CLOSING: "组寝窗口还有 {days} 天关闭",
}

# docs/03 §9.3：SYSTEM 类型的关闭原因 → 标题。
SYSTEM_TITLES: dict[str, str] = {
    "INITIATOR_CANCEL": "对方已撤回请求",
    "END_UNDERSTANDING": "对方已结束了解",
    "TIMEOUT": "请求已过期",
    "FULL": "房间已满，请求已关闭",
    "LOCKED": "房间已锁定，请求已关闭",
    "ROOM_DISSOLVED": "房间已解散",
    "ARCHIVED": "组寝窗口已结束",
    "USER_DISABLED": "对方账号已被禁用",
    "RATE_LIMITED": "请求过于频繁",
    "ADMIN": "请求已被管理员关闭",
    "BLOCKED": "请求已关闭",
    "AUTO_CANCELLED": "你已加入其他寝室",
}

SYSTEM_FALLBACK_TITLE = "请求已关闭"


def normalize_type(notification_type: Any) -> str:
    """校验并返回 ``Notification.Type`` 的字符串值。"""
    raw = str(getattr(notification_type, "value", notification_type) or "").strip()
    value = raw.upper()
    if value not in Notification.Type.values:
        allowed = "/".join(Notification.Type.values)
        raise ValueError(f"未知的通知类型：{raw!r}（可用：{allowed}）")
    return value


def truncate_title(title: Any) -> str:
    """标题截断到模型上限（docs/03 §9.1：昵称/编号超长时截断）。"""
    return str(title or "").strip()[:TITLE_MAX_LENGTH]


def build_title(
    notification_type: Any,
    payload: dict[str, Any] | None = None,
) -> str:
    """按 docs/03 §9 从 type + payload 生成标题。

    ``SYSTEM`` 使用 ``payload.reason`` 映射；原因未知时退回通用文案。
    昵称优先取 ``nickname``，其次 ``from_nickname``（docs/02 §8.3）。
    """

    value = normalize_type(notification_type)
    data = payload or {}
    if value == Notification.Type.SYSTEM:
        reason = str(data.get("reason") or "").strip().upper()
        return truncate_title(SYSTEM_TITLES.get(reason, SYSTEM_FALLBACK_TITLE))

    template = TITLE_TEMPLATES[value]
    nickname = data.get("nickname") or data.get("from_nickname") or "对方"
    room_code = data.get("room_code") or "寝室"
    days = data.get("days_left")
    if days is None:
        days = data.get("days")
    if days is None:
        days = ""
    return truncate_title(
        template.format(
            nickname=nickname,
            room_code=room_code,
            days=days,
        )
    )


def notify(
    user: Any,
    type: Any,  # 契约签名即 notify(user, type, payload, title)；下方只用 value。
    payload: dict[str, Any] | None = None,
    title: Any = None,
) -> Notification:
    """写入一条站内信并返回实例；调用方负责事务边界。

    :param user: 接收者（``User`` 实例或 user_id）。
    :param type: ``Notification.Type`` 值。
    :param payload: 非敏感载荷；命中隐私护栏时抛 ``PayloadNotPublicError``。
    :param title: 可选标题；为空时按 docs/03 §9 自动生成。
    """

    value = normalize_type(type)
    if payload is None:
        data: dict[str, Any] = {}
    else:
        if not isinstance(payload, dict):
            raise ValueError("payload 必须是 JSON 对象")
        data = dict(payload)
    assert_public_payload(data, where="Notification.payload")

    user_id = getattr(user, "pk", user)
    if user_id is None:
        raise ValueError("user 不能为空")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"无法解析通知接收者：{user!r}") from exc

    final_title = truncate_title(title) if title else build_title(value, data)
    return Notification.objects.create(
        user_id=user_id,
        type=value,
        title=final_title,
        payload=data,
    )
