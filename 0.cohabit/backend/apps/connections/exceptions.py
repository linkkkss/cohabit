"""connections 领域异常：直接映射 docs/04 §8 的错误码与 HTTP 状态。

服务层抛这些异常，视图层用 ``accounts_exception_handler`` 输出
``{code, message, detail}`` 信封（与 accounts/rooms/notifications 一致）。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status

from apps.accounts.exceptions import ApiError


class ConnectionError(ApiError):
    """connections 领域异常基类；子类只固定 code/status/默认文案。"""


class ConnectionNotFound(ConnectionError):
    """请求不存在或当前用户非参与者（404 CONNECTION_NOT_FOUND）。

    docs/04 §4.4 / D-04：非参与者与不存在统一 404，不返回 NOT_PARTICIPANT。
    """

    def __init__(self) -> None:
        super().__init__(
            "CONNECTION_NOT_FOUND",
            "请求不存在或当前用户非参与者",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ActionForbidden(ConnectionError):
    """已登录但该动作不允许（403 FORBIDDEN）。"""

    def __init__(self, message: str = "无权执行该操作", detail: Any = None) -> None:
        super().__init__(
            "FORBIDDEN",
            message,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class AccountDisabled(ConnectionError):
    """账号已被禁用（403 ACCOUNT_DISABLED）。"""

    def __init__(self) -> None:
        super().__init__(
            "ACCOUNT_DISABLED",
            "账号已被禁用",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class WrongGender(ConnectionError):
    """性别不一致（403 WRONG_GENDER，docs/04 §8）。"""

    def __init__(self) -> None:
        super().__init__(
            "WRONG_GENDER",
            "只能与同性别同学组寝",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class WrongCollege(ConnectionError):
    """学院不一致（403 WRONG_COLLEGE，docs/04 §8）。"""

    def __init__(self) -> None:
        super().__init__(
            "WRONG_COLLEGE",
            "只能与同学院同学组寝",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class Blocked(ConnectionError):
    """双方存在拉黑（403 BLOCKED）；不暴露是谁拉黑了谁。"""

    def __init__(self) -> None:
        super().__init__(
            "BLOCKED",
            "无法与该用户建立组寝请求",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class UserNotFound(ConnectionError):
    """目标用户不存在或已被禁用（404 USER_NOT_FOUND，X-15 不暴露禁用）。"""

    def __init__(self) -> None:
        super().__init__(
            "USER_NOT_FOUND",
            "用户不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class SelfRequest(ConnectionError):
    """向自己发起请求（400 SELF_REQUEST）。"""

    def __init__(self) -> None:
        super().__init__(
            "SELF_REQUEST",
            "不能向自己发起请求",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class InvalidType(ConnectionError):
    """请求类型与字段组合不合法（400 INVALID_TYPE）。"""

    def __init__(self, message: str = "请求类型与字段组合不合法") -> None:
        super().__init__(
            "INVALID_TYPE",
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class InvalidTarget(ConnectionError):
    """目标结构不合法（400 INVALID_TARGET，``detail.reason`` 细分）。"""

    def __init__(self, reason: str = "", message: str = "目标不合法") -> None:
        detail: dict[str, Any] | None = {"reason": reason} if reason else None
        super().__init__(
            "INVALID_TARGET",
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class CapacityInvalid(ConnectionError):
    """期望容量不是 2/4/6（400 CAPACITY_INVALID）。"""

    def __init__(self, value: Any = None) -> None:
        detail: dict[str, Any] | None = (
            {"capacity_pref": value} if value is not None else None
        )
        super().__init__(
            "CAPACITY_INVALID",
            "期望容量只能是 2/4/6",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class DuplicateRequest(ConnectionError):
    """双方已有在途请求（409 DUPLICATE_REQUEST，X-03 双向）。"""

    def __init__(self) -> None:
        super().__init__(
            "DUPLICATE_REQUEST",
            "你们之间已有处理中的请求",
            status_code=status.HTTP_409_CONFLICT,
        )


class InvalidState(ConnectionError):
    """当前状态不允许该动作（409 INVALID_STATE，``detail.reason`` 细分）。"""

    def __init__(self, reason: str = "", message: str = "当前状态不允许该操作") -> None:
        detail: dict[str, Any] | None = {"reason": reason} if reason else None
        super().__init__(
            "INVALID_STATE",
            message,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class RequestClosed(ConnectionError):
    """对已关闭请求执行动作（409 REQUEST_CLOSED，X-14）。"""

    def __init__(self) -> None:
        super().__init__(
            "REQUEST_CLOSED",
            "请求已结束",
            status_code=status.HTTP_409_CONFLICT,
        )


class RequestExpired(ConnectionError):
    """请求刚被懒过期关闭（409 REQUEST_EXPIRED，X-14）。"""

    def __init__(self) -> None:
        super().__init__(
            "REQUEST_EXPIRED",
            "请求已过期",
            status_code=status.HTTP_409_CONFLICT,
        )


class AlreadyConfirmed(ConnectionError):
    """本人已确认过该请求（409 ALREADY_CONFIRMED，X-02）。"""

    def __init__(self) -> None:
        super().__init__(
            "ALREADY_CONFIRMED",
            "你已确认过该请求",
            status_code=status.HTTP_409_CONFLICT,
        )


class ProfileIncomplete(ConnectionError):
    """本人画像未达 100（409 PROFILE_INCOMPLETE）。"""

    def __init__(self, completeness: int = 0, missing: list[str] | None = None) -> None:
        self.completeness = completeness
        self.missing = list(missing or [])
        super().__init__(
            "PROFILE_INCOMPLETE",
            "请先完善画像再发起组寝",
            status_code=status.HTTP_409_CONFLICT,
            detail={"completeness": completeness, "missing": self.missing[:10]},
        )


class TargetProfileIncomplete(ConnectionError):
    """对方画像未达 100（409 TARGET_PROFILE_INCOMPLETE）。"""

    def __init__(self, completeness: int = 0) -> None:
        self.completeness = completeness
        super().__init__(
            "TARGET_PROFILE_INCOMPLETE",
            "对方画像还未完善",
            status_code=status.HTTP_409_CONFLICT,
            detail={"completeness": completeness},
        )


class RateLimited(ConnectionError):
    """超过在途/每日上限（429 RATE_LIMITED）。"""

    def __init__(self, message: str = "发起请求过于频繁，请稍后再试") -> None:
        super().__init__(
            "RATE_LIMITED",
            message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class Cooldown(ConnectionError):
    """被拒后 24h 冷却（429 COOLDOWN，X-12 双向生效）。"""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(
            "COOLDOWN",
            "对方刚拒绝过请求，24 小时后再试",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=retry_after,
        )


class AlreadyInRoom(ConnectionError):
    """本人已有 ACTIVE 寝室（409 ALREADY_IN_ROOM）。"""

    def __init__(self, message: str = "你已有寝室，需先退出") -> None:
        super().__init__(
            "ALREADY_IN_ROOM",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class TargetInRoom(ConnectionError):
    """目标已有 ACTIVE 寝室（409 TARGET_IN_ROOM，不通知对方）。"""

    def __init__(self, message: str = "对方已有寝室") -> None:
        super().__init__(
            "TARGET_IN_ROOM",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )
