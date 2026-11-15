"""画像写入校验与归一化（docs/03 §2.3–§2.4、§10）。

纯函数：输入客户端 payload + 旧画像，输出规范化后的问卷区块；不读写数据库。
错误统一收集到 ``ProfileValidationError.detail.fields``，最多 20 条。
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any

from apps.profiles.constants import (
    HARD_OPTION_MAP,
    HARD_QUESTION_MAP,
    HARD_QUESTION_ORDER,
    MAX_PROMPTS,
    MAX_RED_LINES,
    MAX_TAGS,
    PROMPT_MAP,
    PROMPT_MAX_LENGTH,
    PROMPT_MAX_LINES,
    PROMPT_ORDER,
    QUESTIONNAIRE_VERSION,
    RED_LINE_MAP,
    RED_LINE_ORDER,
    SOFT_MAX,
    SOFT_MIN,
    SOFT_QUESTION_MAP,
    SOFT_QUESTION_ORDER,
    SUPPORTED_QUESTIONNAIRE_VERSIONS,
    TAG_SET,
)
from apps.profiles.exceptions import (
    PayloadTooLargeError,
    ProfileValidationError,
    field_error,
)
from apps.profiles.constants import PROFILE_MAX_PAYLOAD_BYTES, TAG_ORDER

_UNSET = object()
_HTML_RE = re.compile(r"<[^>]+>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# 允许出现在画像写入 body 的顶层 key；未知 key 按 docs/04 §10 A-05 返回 400。
PROFILE_WRITE_KEYS = frozenset(
    {
        "hard_answers",
        "soft_answers",
        "red_lines",
        "red_lines_confirmed",
        "tags",
        "prompts",
        "questionnaire_version",
        "dims",
        "completeness",
    }
)


@dataclass
class ProfileData:
    """规范化后的画像问卷区块（不含服务端计算的 dims/completeness）。"""

    hard_answers: dict[str, str] = field(default_factory=dict)
    soft_answers: dict[str, int] = field(default_factory=dict)
    red_lines: list[str] = field(default_factory=list)
    red_lines_confirmed: bool = False
    tags: list[str] = field(default_factory=list)
    prompts: dict[str, str] = field(default_factory=dict)
    questionnaire_version: str = QUESTIONNAIRE_VERSION


def _defaults() -> ProfileData:
    return ProfileData()


def _existing_data(existing: Any) -> ProfileData:
    """把 Profile 实例或等价 dict 转成 ``ProfileData``（做深拷贝）。"""
    if existing is None:
        return _defaults()
    getter = existing.get if isinstance(existing, dict) else lambda key, default=None: getattr(
        existing, key, default
    )
    return ProfileData(
        hard_answers=copy.deepcopy(getter("hard_answers", {}) or {}),
        soft_answers=copy.deepcopy(getter("soft_answers", {}) or {}),
        red_lines=copy.deepcopy(getter("red_lines", []) or []),
        red_lines_confirmed=getter("red_lines_confirmed", False) is True,
        tags=copy.deepcopy(getter("tags", []) or []),
        prompts=copy.deepcopy(getter("prompts", {}) or {}),
        questionnaire_version=getter("questionnaire_version", QUESTIONNAIRE_VERSION),
    )


def payload_size_bytes(payload: Any) -> int:
    """按 UTF-8 JSON 计算提交体大小（无法序列化时按最大计）。"""
    try:
        return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return PROFILE_MAX_PAYLOAD_BYTES + 1


def _text_error(message: str) -> dict[str, Any]:
    return field_error("INVALID_TEXT", message)


def _validate_text(value: str, *, allow_newlines: bool = False) -> str | None:
    """去首尾空白并做控制字符/HTML/长度以外的基础文本检查。"""
    text = value.strip()
    control_target = text if allow_newlines else text.replace("\n", "").replace("\r", "")
    if _CONTROL_RE.search(control_target):
        return None
    if "\x00" in text:
        return None
    if _HTML_RE.search(text):
        return None
    return text


def _normalize_hard(
    raw: Any,
    base: dict[str, str],
    errors: dict[str, dict[str, Any]],
) -> dict[str, str]:
    if not isinstance(raw, dict):
        errors["hard_answers"] = field_error("VALIDATION_ERROR", "hard_answers 必须是对象。")
        return base
    target = dict(base)
    for key, value in raw.items():
        path = f"hard_answers.{key}"
        if key not in HARD_QUESTION_MAP:
            errors[path] = field_error(
                "UNKNOWN_ANSWER_KEY",
                allowed=list(HARD_QUESTION_ORDER),
            )
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            target.pop(key, None)
            continue
        if not isinstance(value, str) or value not in HARD_OPTION_MAP[key]:
            errors[path] = field_error(
                "INVALID_OPTION",
                allowed=list(HARD_OPTION_MAP[key]),
            )
            continue
        target[key] = value
    return {key: target[key] for key in HARD_QUESTION_ORDER if key in target}


def _normalize_soft(
    raw: Any,
    base: dict[str, int],
    errors: dict[str, dict[str, Any]],
) -> dict[str, int]:
    if not isinstance(raw, dict):
        errors["soft_answers"] = field_error("VALIDATION_ERROR", "soft_answers 必须是对象。")
        return base
    target = dict(base)
    for key, value in raw.items():
        path = f"soft_answers.{key}"
        if key not in SOFT_QUESTION_MAP:
            errors[path] = field_error(
                "UNKNOWN_ANSWER_KEY",
                allowed=list(SOFT_QUESTION_ORDER),
            )
            continue
        # bool 是 int 子类，必须显式拒绝（docs/03 V-03）。
        if isinstance(value, bool) or not isinstance(value, int):
            errors[path] = field_error(
                "INVALID_SOFT_VALUE",
                min=SOFT_MIN,
                max=SOFT_MAX,
            )
            continue
        if not SOFT_MIN <= value <= SOFT_MAX:
            errors[path] = field_error(
                "INVALID_SOFT_VALUE",
                min=SOFT_MIN,
                max=SOFT_MAX,
            )
            continue
        target[key] = value
    return {key: target[key] for key in SOFT_QUESTION_ORDER if key in target}


def _normalize_red_lines(
    raw: Any,
    errors: dict[str, dict[str, Any]],
) -> list[str] | None:
    if not isinstance(raw, list):
        errors["red_lines"] = field_error(
            "INVALID_RED_LINE",
            allowed=list(RED_LINE_ORDER),
        )
        return None
    normalized: list[str] = []
    for item in raw:
        if not isinstance(item, str) or item not in RED_LINE_MAP:
            errors["red_lines"] = field_error(
                "INVALID_RED_LINE",
                allowed=list(RED_LINE_ORDER),
            )
            continue
        if item not in normalized:
            normalized.append(item)
    if len(normalized) > MAX_RED_LINES:
        errors["red_lines"] = field_error(
            "INVALID_RED_LINE",
            max=MAX_RED_LINES,
        )
        return None
    return sorted(normalized, key=RED_LINE_ORDER.index)


def _normalize_tags(
    raw: Any,
    errors: dict[str, dict[str, Any]],
) -> list[str]:
    if not isinstance(raw, list):
        errors["tags"] = field_error("INVALID_TAG", allowed=list(TAG_ORDER))
        return []
    normalized: list[str] = []
    for item in raw:
        if not isinstance(item, str) or item not in TAG_SET:
            errors["tags"] = field_error("INVALID_TAG", allowed=list(TAG_ORDER))
            continue
        if item not in normalized:
            normalized.append(item)
    if len(normalized) > MAX_TAGS:
        errors["tags"] = field_error("TAG_LIMIT", max=MAX_TAGS)
        return []
    return sorted(normalized, key=TAG_ORDER.index)


def _prompt_has_too_many_lines(text: str) -> bool:
    return len(text.splitlines()) > PROMPT_MAX_LINES


def _normalize_prompts(
    raw: Any,
    errors: dict[str, dict[str, Any]],
) -> dict[str, str]:
    if not isinstance(raw, dict):
        errors["prompts"] = field_error("VALIDATION_ERROR", "prompts 必须是对象。")
        return {}
    target: dict[str, str] = {}
    for key, value in raw.items():
        path = f"prompts.{key}"
        if key not in PROMPT_MAP:
            errors[path] = field_error(
                "INVALID_PROMPT_KEY",
                allowed=list(PROMPT_ORDER),
            )
            continue
        if not isinstance(value, str):
            errors[path] = _text_error("prompt 必须是文本。")
            continue
        text = value.strip()
        if not text:
            continue
        if len(text) > PROMPT_MAX_LENGTH:
            errors[path] = field_error("PROMPT_TOO_LONG", max=PROMPT_MAX_LENGTH)
            continue
        if _prompt_has_too_many_lines(text):
            errors[path] = _text_error(f"prompt 最多 {PROMPT_MAX_LINES} 行。")
            continue
        cleaned = _validate_text(text, allow_newlines=True)
        if cleaned is None:
            errors[path] = _text_error("prompt 包含不支持的字符或 HTML。")
            continue
        target[key] = cleaned
    if len(target) > MAX_PROMPTS:
        errors["prompts"] = field_error(
            "VALIDATION_ERROR",
            f"最多 {MAX_PROMPTS} 条 prompt。",
            max=MAX_PROMPTS,
        )
        return {}
    return {key: target[key] for key in PROMPT_ORDER if key in target}


def _normalize_version(
    raw: Any,
    errors: dict[str, dict[str, Any]],
) -> str:
    if raw is not _UNSET:
        if not isinstance(raw, str) or raw not in SUPPORTED_QUESTIONNAIRE_VERSIONS:
            errors["questionnaire_version"] = field_error(
                "QUESTIONNAIRE_VERSION_UNSUPPORTED",
                allowed=sorted(SUPPORTED_QUESTIONNAIRE_VERSIONS),
            )
    return QUESTIONNAIRE_VERSION


def validate_profile_payload(
    payload: Any,
    *,
    partial: bool = False,
    existing: Any = None,
) -> ProfileData:
    """校验并归一化画像写入。

    - ``partial=False``（PUT）：未提供的问卷字段按空值处理；
    - ``partial=True``（PATCH）：未提供的字段保留旧值；``hard_answers``/
      ``soft_answers`` 按 key 合并，``red_lines``/``tags``/``prompts`` 提供即整体替换；
    - ``dims``/``completeness`` 客户端传了也忽略；
    - ``red_lines`` 变更且未显式 ``red_lines_confirmed=true`` 时，确认状态置 false。
    """
    if not isinstance(payload, dict):
        raise ProfileValidationError(
            {"body": field_error("VALIDATION_ERROR", "请求体必须是 JSON 对象。")}
        )
    size = payload_size_bytes(payload)
    if size > PROFILE_MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(PROFILE_MAX_PAYLOAD_BYTES)

    unknown = sorted(set(payload) - PROFILE_WRITE_KEYS)
    if unknown:
        raise ProfileValidationError(
            {key: field_error("UNKNOWN_FIELD") for key in unknown}
        )

    old = _existing_data(existing)
    data = _existing_data(existing) if partial else _defaults()
    errors: dict[str, dict[str, Any]] = {}

    if "hard_answers" in payload:
        data.hard_answers = _normalize_hard(
            payload["hard_answers"],
            data.hard_answers if partial else {},
            errors,
        )
    if "soft_answers" in payload:
        data.soft_answers = _normalize_soft(
            payload["soft_answers"],
            data.soft_answers if partial else {},
            errors,
        )

    red_lines_changed = False
    if "red_lines" in payload:
        normalized_red_lines = _normalize_red_lines(payload["red_lines"], errors)
        if normalized_red_lines is not None:
            red_lines_changed = normalized_red_lines != old.red_lines
            data.red_lines = normalized_red_lines

    confirmed_provided = "red_lines_confirmed" in payload
    if confirmed_provided:
        confirmed = payload["red_lines_confirmed"]
        if not isinstance(confirmed, bool):
            errors["red_lines_confirmed"] = field_error("INVALID_BOOLEAN")
        else:
            data.red_lines_confirmed = confirmed
    if red_lines_changed and not (
        confirmed_provided and data.red_lines_confirmed is True
    ):
        data.red_lines_confirmed = False

    if "tags" in payload:
        data.tags = _normalize_tags(payload["tags"], errors)
    if "prompts" in payload:
        data.prompts = _normalize_prompts(payload["prompts"], errors)
    if "questionnaire_version" in payload:
        data.questionnaire_version = _normalize_version(
            payload["questionnaire_version"],
            errors,
        )
    else:
        data.questionnaire_version = QUESTIONNAIRE_VERSION

    if errors:
        raise ProfileValidationError(errors)
    return data
