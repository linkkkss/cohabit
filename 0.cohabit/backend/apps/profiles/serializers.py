"""画像/问卷/联系方式的序列化（docs/04 §3.3–§3.5、§4.1）。"""

from __future__ import annotations

import re
from typing import Any

from rest_framework import serializers

from apps.accounts.models import ContactInfo
from apps.accounts.serializers import UserSummarySerializer
from apps.profiles.constants import (
    PROMPT_MAX_LENGTH,
    PROMPT_ORDER,
    QUESTIONNAIRE_VERSION,
)
from apps.profiles.models import Profile

HEADLINE_MAX_LENGTH = 60
QQ_RE = re.compile(r"^\d{5,12}$")
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class ProfileSerializer(serializers.ModelSerializer):
    """``Profile`` 响应体：问卷字段只读服务端计算结果。"""

    class Meta:
        model = Profile
        fields = (
            "hard_answers",
            "soft_answers",
            "red_lines",
            "red_lines_confirmed",
            "tags",
            "prompts",
            "dims",
            "completeness",
            "questionnaire_version",
        )
        read_only_fields = fields


class ContactInfoSerializer(serializers.ModelSerializer):
    """``ContactInfo`` 响应/写入；``null`` 表示清空，``show_*`` 仅本人可见。"""

    class Meta:
        model = ContactInfo
        fields = ("qq", "wechat", "phone", "show_qq", "show_wechat", "show_phone")
        extra_kwargs = {
            "qq": {"required": False, "allow_null": True, "allow_blank": True},
            "wechat": {"required": False, "allow_null": True, "allow_blank": True},
            "phone": {"required": False, "allow_null": True, "allow_blank": True},
        }

    @staticmethod
    def _blank_to_none(value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    def validate_qq(self, value: str | None) -> str | None:
        text = self._blank_to_none(value)
        if text is not None and not QQ_RE.match(text):
            raise serializers.ValidationError("QQ 必须是 5–12 位数字。")
        return text

    def validate_wechat(self, value: str | None) -> str | None:
        return self._blank_to_none(value)

    def validate_phone(self, value: str | None) -> str | None:
        text = self._blank_to_none(value)
        if text is not None and not PHONE_RE.match(text):
            raise serializers.ValidationError("手机号必须是 11 位中国大陆号码。")
        return text


def headline_for(profile: Profile | None) -> str | None:
    """按 ``PROMPT_ORDER`` 取第一条非空 prompt，截断 60 字（docs/04 §4.2）。"""
    if profile is None:
        return None
    prompts = profile.prompts if isinstance(profile.prompts, dict) else {}
    for key in PROMPT_ORDER:
        value = prompts.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:HEADLINE_MAX_LENGTH]
    return None


def public_user_payload(user: Any) -> dict[str, Any]:
    """``GET /api/users/:uid`` 的公开摘要：无 contact/email/dims/red_lines。"""
    profile = getattr(user, "profile", None)
    payload: dict[str, Any] = dict(UserSummarySerializer(user).data)
    payload.update(
        {
            "tags": list(profile.tags or []) if profile else [],
            "headline": headline_for(profile),
            "prompts": dict(profile.prompts or {}) if profile else {},
            "completeness": int(profile.completeness or 0) if profile else 0,
        }
    )
    return payload


def questionnaire_version_of(profile: Profile | None) -> str:
    return str(
        getattr(profile, "questionnaire_version", None) or QUESTIONNAIRE_VERSION
    )


__all__ = [
    "ContactInfoSerializer",
    "HEADLINE_MAX_LENGTH",
    "PROMPT_MAX_LENGTH",
    "ProfileSerializer",
    "headline_for",
    "public_user_payload",
    "questionnaire_version_of",
]
