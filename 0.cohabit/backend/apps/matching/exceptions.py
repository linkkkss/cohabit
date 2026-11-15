"""匹配领域异常（docs/03 §8.7、docs/04 §4.2/§8）。"""

from __future__ import annotations

from typing import Any

MATCH_MESSAGES = {
    "INVALID_TARGET": "目标不合法。",
    "PROFILE_INCOMPLETE": "请先完成画像，才能开始匹配。",
    "PROFILE_NOT_FOUND": "画像不存在。",
    "TARGET_PROFILE_INCOMPLETE": "对方画像尚未完成。",
    "TARGET_IN_ROOM": "对方已有寝室。",
    "BLOCKED": "你们之间存在拉黑关系。",
    "USER_NOT_FOUND": "用户不存在。",
}


class MatchError(Exception):
    """匹配服务错误；API 层直接映射 ``{code, message, detail}``。"""

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        status_code: int = 400,
        detail: Any = None,
    ) -> None:
        self.code = code
        self.message = message or MATCH_MESSAGES.get(code, "请求未完成")
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class InvalidTargetError(MatchError):
    def __init__(self, reason: str = "SELF") -> None:
        super().__init__(
            "INVALID_TARGET",
            status_code=400,
            detail={"reason": reason},
        )


class ProfileIncompleteError(MatchError):
    def __init__(self, completeness: int, missing: list[str] | None = None) -> None:
        detail: dict[str, Any] = {"completeness": completeness}
        if missing:
            detail["missing"] = missing[:10]
        # 本人画像未完成：403（docs/04 §4.2 v1.1，captain m00879 裁决）。
        super().__init__("PROFILE_INCOMPLETE", status_code=403, detail=detail)


class ProfileNotFoundError(MatchError):
    def __init__(self) -> None:
        super().__init__("PROFILE_NOT_FOUND", status_code=404)


class TargetProfileIncompleteError(MatchError):
    def __init__(self, completeness: int) -> None:
        super().__init__(
            "TARGET_PROFILE_INCOMPLETE",
            status_code=409,
            detail={"completeness": completeness},
        )


class TargetInRoomError(MatchError):
    def __init__(self, target_uid: str) -> None:
        super().__init__(
            "TARGET_IN_ROOM",
            status_code=409,
            detail={"target_uid": target_uid},
        )


class BlockedError(MatchError):
    def __init__(self) -> None:
        super().__init__("BLOCKED", status_code=403)
