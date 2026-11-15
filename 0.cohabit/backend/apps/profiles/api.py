"""画像/匹配 API 共用出口：领域异常统一映射为 docs/04 §1.6 错误信封。"""

from __future__ import annotations

from typing import Any

from rest_framework.views import APIView

from apps.accounts.exceptions import ApiError, accounts_exception_handler
from apps.matching.exceptions import MatchError
from apps.profiles.exceptions import ProfileError


def domain_to_api_error(exc: BaseException) -> ApiError | None:
    """把领域异常转换为携带契约错误码的 ``ApiError``；其它异常返回 ``None``。"""
    if isinstance(exc, (ProfileError, MatchError)):
        return ApiError(
            exc.code,
            getattr(exc, "message", None),
            status_code=getattr(exc, "status_code", None),
            detail=getattr(exc, "detail", None),
        )
    return None


class DomainAPIView(APIView):
    """领域视图基类：错误码/状态与 accounts 认证端点保持一致的信封。"""

    def get_exception_handler(self) -> Any:
        return accounts_exception_handler

    def handle_exception(self, exc: Exception) -> Any:
        mapped = domain_to_api_error(exc)
        if mapped is None:
            return super().handle_exception(exc)
        context = {"request": self.request, "view": self, "args": (), "kwargs": {}}
        return accounts_exception_handler(mapped, context)
