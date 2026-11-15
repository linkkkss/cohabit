"""accounts API 异常层：把领域错误映射为 docs/04 §1.6/§8 的错误信封与错误码。"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import ExpiredTokenError, InvalidToken, TokenError

from config.api import api_exception_handler

# 与 docs/04 §8 对齐的稳定错误消息。
_MESSAGES = {
    "VALIDATION_ERROR": "请求参数不合法",
    "CODE_INVALID": "验证码错误",
    "CODE_EXPIRED": "验证码已过期，请重新获取",
    "INVITE_INVALID": "邀请码无效",
    "INVITE_REQUIRED": "需要邀请码才能注册",
    "EMAIL_TAKEN": "该邮箱已被注册",
    "AUTH_REQUIRED": "需要登录",
    "TOKEN_EXPIRED": "登录已过期，请重新登录",
    "TOKEN_INVALID": "登录凭证无效",
    "INVALID_CREDENTIALS": "邮箱或密码错误",
    "FORBIDDEN": "来源不被允许",
    "GENDER_IMMUTABLE": "性别注册后不可修改",
    "ACCOUNT_DISABLED": "账号已被禁用",
    "RATE_LIMITED": "请求过于频繁，请稍后再试",
    "THROTTLED": "请求过于频繁，请稍后再试",
}


class ApiError(APIException):
    """携带契约错误码的业务异常；响应体固定为 ``{code, message, detail}``。"""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        code: str,
        message: str | None = None,
        status_code: int | None = None,
        detail: Any = None,
        retry_after: int | None = None,
    ) -> None:
        self.error_code = code
        self.error_message = message or _MESSAGES.get(code, "请求未完成")
        self.error_detail = detail
        self.retry_after = retry_after
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=detail if detail is not None else self.error_message, code=code.lower())


def _first_message(data: Any) -> str:
    """从 DRF 的嵌套 detail 中取第一条字符串，作为信封的 message。"""
    if isinstance(data, dict):
        for value in data.values():
            text = _first_message(value)
            if text:
                return text
    elif isinstance(data, (list, tuple)):
        for value in data:
            text = _first_message(value)
            if text:
                return text
    elif isinstance(data, str):
        return data
    return ""


def _token_response(code: str) -> Response:
    return Response(
        {"code": code, "message": _MESSAGES[code], "detail": None},
        status=status.HTTP_401_UNAUTHORIZED,
    )


def _is_expired(exc: TokenError | InvalidToken) -> bool:
    if isinstance(exc, ExpiredTokenError):
        return True
    detail = getattr(exc, "detail", None) or exc
    return "expired" in str(detail).lower()


def accounts_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """accounts 视图的统一异常出口；未识别时退回 config.api 的全局信封。"""
    if isinstance(exc, ApiError):
        response = Response(
            {"code": exc.error_code, "message": exc.error_message, "detail": exc.error_detail},
            status=exc.status_code,
        )
        if exc.retry_after is not None:
            response["Retry-After"] = str(exc.retry_after)
        return response
    if isinstance(exc, InvalidToken):
        return _token_response("TOKEN_EXPIRED" if _is_expired(exc) else "TOKEN_INVALID")
    if isinstance(exc, TokenError):
        return _token_response("TOKEN_EXPIRED" if _is_expired(exc) else "TOKEN_INVALID")
    if isinstance(exc, NotAuthenticated):
        return Response(
            {"code": "AUTH_REQUIRED", "message": _MESSAGES["AUTH_REQUIRED"], "detail": None},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if isinstance(exc, AuthenticationFailed):
        # SimpleJWT 对 is_active=False 的用户抛 user_inactive：按契约返回 403。
        code = getattr(exc, "default_code", "") or ""
        if code == "user_inactive" or "inactive" in str(getattr(exc, "detail", "")).lower():
            return Response(
                {"code": "ACCOUNT_DISABLED", "message": _MESSAGES["ACCOUNT_DISABLED"], "detail": None},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {"code": "INVALID_CREDENTIALS", "message": _MESSAGES["INVALID_CREDENTIALS"], "detail": None},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if isinstance(exc, PermissionDenied):
        return Response(
            {"code": "FORBIDDEN", "message": _MESSAGES["FORBIDDEN"], "detail": None},
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, ValidationError):
        fields = getattr(exc, "detail", None)
        return Response(
            {
                "code": "VALIDATION_ERROR",
                "message": _first_message(fields) or _MESSAGES["VALIDATION_ERROR"],
                "detail": {"fields": fields},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return api_exception_handler(exc, context)
