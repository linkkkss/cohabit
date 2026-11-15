"""组寝时间窗判定（docs/02 §7、docs/04 §1.8）。

规则（docs/02 §7.1/§7.2）：

* 按学院配置，一个学院最多一条 ``TimeWindow``；
* **无记录 = 关闭**；``now < start_at`` 或 ``now >= end_at`` 均关闭；
* 每次写操作实时查询，不做长缓存（请求级缓存可选，但事务内必须重读）；
* 只约束组寝写操作；注册/登录、资料/问卷编辑、举报/拉黑、通知已读不受影响；
* 关闭时写操作返回 ``409 WINDOW_CLOSED``，读接口正常。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone
from rest_framework import status

from apps.accounts.exceptions import ApiError
from apps.adminops.models import TimeWindow


class WindowClosed(ApiError):
    """时间窗未开放：``409 WINDOW_CLOSED``（docs/04 §1.6/§8）。"""

    status_code = status.HTTP_409_CONFLICT
    default_code = "WINDOW_CLOSED"
    default_detail = "当前不在组寝开放时间内"

    def __init__(self, message: str | None = None, detail: Any = None) -> None:
        super().__init__(
            "WINDOW_CLOSED",
            message or self.default_detail,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


def _normalize_at(at: datetime | None) -> datetime:
    """统一为 aware datetime；裸 ``datetime`` 按项目时区解释。"""
    if at is None:
        return timezone.now()
    if timezone.is_naive(at):
        return timezone.make_aware(at, timezone.get_current_timezone())
    return at


def get_open_window(
    college: Any,
    at: datetime | None = None,
) -> TimeWindow | None:
    """返回该学院当前有效的窗口；未配置或不在区间内返回 ``None``。"""

    if not college:
        return None
    now = _normalize_at(at)
    window = TimeWindow.objects.filter(college=str(college)).first()
    if window is None or not (window.start_at <= now < window.end_at):
        return None
    return window


def is_window_open(college: Any, at: datetime | None = None) -> bool:
    """该学院在 ``at``（默认当前时间）是否允许组寝写操作。"""
    return get_open_window(college, at) is not None


def require_window_open(college: Any, at: datetime | None = None) -> TimeWindow:
    """校验窗口开放并返回窗口；关闭时抛 :class:`WindowClosed`。

    仅供组寝写操作调用（创建请求/accept/decline/cancel/confirm、锁定/解锁、
    退出/移除/解散/转让）；通知已读等读接口不得调用。
    """

    window = get_open_window(college, at)
    if window is None:
        raise WindowClosed()
    return window
