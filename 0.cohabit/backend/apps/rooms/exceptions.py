"""rooms 领域异常：直接映射 docs/04 §8 的错误码与 HTTP 状态。

服务层抛这些异常，视图层用 ``accounts_exception_handler`` 输出
``{code, message, detail}`` 信封（与 accounts/notifications 一致）。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status

from apps.accounts.exceptions import ApiError


class RoomError(ApiError):
    """rooms 领域异常基类；子类只固定 code/status/默认文案。"""


class RoomNotFound(RoomError):
    """寝室不存在或对当前用户不可见（docs/04 §8：404 ROOM_NOT_FOUND）。"""

    def __init__(self, detail: Any = None) -> None:
        super().__init__(
            "ROOM_NOT_FOUND",
            "寝室不存在",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class TransferNotFound(RoomError):
    """转让不存在或不属于当前用户的寝室（404 TRANSFER_NOT_FOUND）。"""

    def __init__(self, detail: Any = None) -> None:
        super().__init__(
            "TRANSFER_NOT_FOUND",
            "转让不存在",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class NotOwner(RoomError):
    """非房主执行房主动作（403 NOT_OWNER）。"""

    def __init__(self, detail: Any = None) -> None:
        super().__init__(
            "NOT_OWNER",
            "只有房主可以执行该操作",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class NotMember(RoomError):
    """非本寝成员执行成员动作（403 NOT_MEMBER）。"""

    def __init__(self, detail: Any = None) -> None:
        super().__init__(
            "NOT_MEMBER",
            "你不是该寝成员",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ActionForbidden(RoomError):
    """已登录但动作不允许（403 FORBIDDEN）。"""

    def __init__(self, message: str = "无权执行该操作", detail: Any = None) -> None:
        super().__init__(
            "FORBIDDEN",
            message,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class InvalidState(RoomError):
    """当前状态不允许该动作（409 INVALID_STATE，``detail.reason`` 细分）。"""

    def __init__(self, reason: str = "", message: str = "当前状态不允许该操作") -> None:
        detail: dict[str, Any] | None = {"reason": reason} if reason else None
        super().__init__(
            "INVALID_STATE",
            message,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class RoomFull(RoomError):
    """寝室已满（409 ROOM_FULL）。"""

    def __init__(self, room_code: str | None = None) -> None:
        detail = {"room_code": room_code} if room_code else None
        super().__init__(
            "ROOM_FULL",
            "寝室已满员",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class RoomLocked(RoomError):
    """寝室已锁定（409 ROOM_LOCKED）。"""

    def __init__(self, room_code: str | None = None) -> None:
        detail = {"room_code": room_code} if room_code else None
        super().__init__(
            "ROOM_LOCKED",
            "寝室已锁定",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class RoomArchived(RoomError):
    """寝室已归档（409 ROOM_ARCHIVED）。"""

    def __init__(self, room_code: str | None = None) -> None:
        detail = {"room_code": room_code} if room_code else None
        super().__init__(
            "ROOM_ARCHIVED",
            "寝室已归档",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class RoomDissolved(RoomError):
    """寝室已解散（409 ROOM_DISSOLVED）。"""

    def __init__(self, room_code: str | None = None) -> None:
        detail = {"room_code": room_code} if room_code else None
        super().__init__(
            "ROOM_DISSOLVED",
            "寝室已解散",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class AlreadyInRoom(RoomError):
    """本人已有 ACTIVE 寝室（409 ALREADY_IN_ROOM）。"""

    def __init__(self, uid: str | None = None) -> None:
        detail = {"uid": uid} if uid else None
        super().__init__(
            "ALREADY_IN_ROOM",
            "你已有寝室",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class TargetInRoom(RoomError):
    """目标已有 ACTIVE 寝室（409 TARGET_IN_ROOM）。"""

    def __init__(self, uid: str | None = None) -> None:
        detail = {"uid": uid} if uid else None
        super().__init__(
            "TARGET_IN_ROOM",
            "对方已有寝室",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class OwnerMustTransferOrDissolve(RoomError):
    """房主不能直接退出（409 OWNER_MUST_TRANSFER_OR_DISSOLVE）。"""

    def __init__(self) -> None:
        super().__init__(
            "OWNER_MUST_TRANSFER_OR_DISSOLVE",
            "房主需先转让房主或解散寝室",
            status_code=status.HTTP_409_CONFLICT,
        )


class CannotRemoveOwner(RoomError):
    """不能移除房主（409 CANNOT_REMOVE_OWNER）。"""

    def __init__(self) -> None:
        super().__init__(
            "CANNOT_REMOVE_OWNER",
            "不能移除房主",
            status_code=status.HTTP_409_CONFLICT,
        )


class TransferExists(RoomError):
    """同寝已有 PENDING 转让（409 TRANSFER_EXISTS）。"""

    def __init__(self) -> None:
        super().__init__(
            "TRANSFER_EXISTS",
            "该寝室已有待处理的房主转让",
            status_code=status.HTTP_409_CONFLICT,
        )


class TransferExpired(RoomError):
    """转让已过期（409 TRANSFER_EXPIRED）。"""

    def __init__(self) -> None:
        super().__init__(
            "TRANSFER_EXPIRED",
            "房主转让已过期",
            status_code=status.HTTP_409_CONFLICT,
        )


class CapacityImmutable(RoomError):
    """试图修改容量（409 CAPACITY_IMMUTABLE）。"""

    def __init__(self) -> None:
        super().__init__(
            "CAPACITY_IMMUTABLE",
            "寝室容量不可修改",
            status_code=status.HTTP_409_CONFLICT,
            detail={"field": "capacity"},
        )


class InvalidTarget(RoomError):
    """目标不合法（400 INVALID_TARGET，``detail.reason`` 细分）。"""

    def __init__(self, reason: str = "", message: str = "目标不合法") -> None:
        detail: dict[str, Any] | None = {"reason": reason} if reason else None
        super().__init__(
            "INVALID_TARGET",
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class CapacityInvalid(RoomError):
    """容量不是 2/4/6（400 CAPACITY_INVALID）。"""

    def __init__(self, value: Any = None) -> None:
        detail: dict[str, Any] | None = {"capacity": value} if value is not None else None
        super().__init__(
            "CAPACITY_INVALID",
            "容量只能是 2/4/6",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class RoomCodeGenerationFailed(RoomError):
    """9 位码连续碰撞（500 ROOM_CODE_GENERATION_FAILED）。"""

    def __init__(self) -> None:
        super().__init__(
            "ROOM_CODE_GENERATION_FAILED",
            "寝室号生成失败，请重试",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class RoomRateLimited(RoomError):
    """当日创建寝室次数超限（429 RATE_LIMITED，带 ``Retry-After``）。"""

    def __init__(self, limit: int = 5, retry_after: int | None = None) -> None:
        super().__init__(
            "RATE_LIMITED",
            f"今日创建寝室次数已达上限（{limit} 次）",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=retry_after,
        )
