"""通知 API 的契约错误码（docs/04 §4.5、§8）。"""

from __future__ import annotations

from rest_framework import status

from apps.accounts.exceptions import ApiError


class NotificationNotFound(ApiError):
    """通知不存在或不属于当前用户。

    两种情形统一返回 ``404 NOTIFICATION_NOT_FOUND``，不泄露他人通知的存在性。
    """

    def __init__(self) -> None:
        super().__init__(
            "NOTIFICATION_NOT_FOUND",
            "通知不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )
