"""画像/问卷校验异常（docs/03 §10）。

异常不依赖 DRF：API 层（B6）可以把 ``code/message/detail`` 直接映射为
``{code, message, detail}`` 信封；纯函数测试也可直接断言字段级错误。
"""

from __future__ import annotations

from typing import Any

VALIDATION_MESSAGE = "画像提交有误，请检查后重试。"

# docs/03 §10.2 的 HTTP 状态；PAYLOAD_TOO_LARGE 在 03 中为 413。
STATUS_CODE_BY_ERROR = {
    "UNKNOWN_ANSWER_KEY": 400,
    "INVALID_OPTION": 400,
    "INVALID_SOFT_VALUE": 400,
    "INVALID_RED_LINE": 400,
    "INVALID_BOOLEAN": 400,
    "INVALID_TAG": 400,
    "TAG_LIMIT": 400,
    "INVALID_PROMPT_KEY": 400,
    "PROMPT_TOO_LONG": 400,
    "QUESTIONNAIRE_VERSION_UNSUPPORTED": 400,
    "INVALID_TEXT": 400,
    "UNKNOWN_FIELD": 400,
    "PAYLOAD_TOO_LARGE": 413,
    "VALIDATION_ERROR": 400,
    "PROFILE_INCOMPLETE": 409,
    "PROFILE_NOT_FOUND": 404,
    "TARGET_IN_ROOM": 409,
    "INVALID_TARGET": 400,
}

ERROR_MESSAGES = {
    "UNKNOWN_ANSWER_KEY": "存在未知的题目 key。",
    "INVALID_OPTION": "不支持的选项。",
    "INVALID_SOFT_VALUE": "软指标必须是 1–5 的整数。",
    "INVALID_RED_LINE": "红线选择不合法。",
    "INVALID_BOOLEAN": "确认字段必须是布尔值。",
    "INVALID_TAG": "标签不在词库中。",
    "TAG_LIMIT": "标签最多 8 个。",
    "INVALID_PROMPT_KEY": "prompt key 不在题库中。",
    "PROMPT_TOO_LONG": "prompt 最多 120 字。",
    "QUESTIONNAIRE_VERSION_UNSUPPORTED": "问卷版本不支持。",
    "INVALID_TEXT": "文本包含不支持的内容。",
    "UNKNOWN_FIELD": "存在未知字段。",
    "PAYLOAD_TOO_LARGE": "提交体过大。",
    "VALIDATION_ERROR": "请求参数不合法。",
    "PROFILE_INCOMPLETE": "请先完成画像，才能开始匹配。",
    "PROFILE_NOT_FOUND": "画像不存在。",
    "TARGET_IN_ROOM": "对方已有寝室。",
    "INVALID_TARGET": "目标不合法。",
}

MAX_FIELD_ERRORS = 20


class ProfileError(Exception):
    """画像领域的通用异常，携带契约错误码与结构化 detail。"""

    code: str = "VALIDATION_ERROR"
    status_code: int = 400

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        detail: Any = None,
        status_code: int | None = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "请求未完成")
        self.detail = detail
        self.status_code = status_code or STATUS_CODE_BY_ERROR.get(code, 400)
        super().__init__(self.message)


def field_error(
    code: str,
    message: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """构造单个字段错误；``extra`` 为 ``allowed``/``max`` 等补充信息。"""
    payload: dict[str, Any] = {
        "code": code,
        "message": message or ERROR_MESSAGES.get(code, "不合法。"),
    }
    payload.update(extra)
    return payload


class ProfileValidationError(ProfileError):
    """一次返回多个字段错误（最多 20 条，超出截断并标记 truncated）。"""

    def __init__(self, fields: dict[str, dict[str, Any]]) -> None:
        all_fields = dict(fields)
        truncated = len(all_fields) > MAX_FIELD_ERRORS
        limited = dict(list(all_fields.items())[:MAX_FIELD_ERRORS])
        first = next(iter(limited.values()))
        detail: dict[str, Any] = {"fields": limited}
        if truncated:
            detail["truncated"] = True
        super().__init__(
            first.get("code", "VALIDATION_ERROR"),
            VALIDATION_MESSAGE,
            detail=detail,
            status_code=400,
        )
        self.fields = limited
        self.truncated = truncated


class PayloadTooLargeError(ProfileError):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(
            "PAYLOAD_TOO_LARGE",
            detail={"max_bytes": max_bytes},
            status_code=413,
        )


class ProfileIncompleteError(ProfileError):
    def __init__(self, completeness: int, missing: list[str]) -> None:
        super().__init__(
            "PROFILE_INCOMPLETE",
            detail={"completeness": completeness, "missing": missing[:10]},
            status_code=409,
        )
        self.completeness = completeness
        self.missing = missing[:10]
