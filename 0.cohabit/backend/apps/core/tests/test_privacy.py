"""隐私护栏单元测试（docs/02 §8.1、docs/03 §9.4）。"""

from __future__ import annotations

import pytest

from apps.core.privacy import (
    PayloadNotPublicError,
    assert_public_payload,
    is_forbidden_key,
    normalize_key,
)


@pytest.mark.parametrize(
    "key",
    [
        "email",
        "qq",
        "wechat",
        "wechat_id",
        "phone",
        "phone_number",
        "mobile",
        "tel",
        "contact",
        "contact_info",
        "real_name",
        "realname",
        "id_card",
        "token",
        "access_token",
        "refresh_token",
        "jwt",
        "password",
        "session_id",
        "ip",
        "ip_address",
        "user_agent",
    ],
)
def test_exact_forbidden_keys(key):
    assert is_forbidden_key(key) is True


@pytest.mark.parametrize(
    "key",
    ["user_email", "contact_phone", "owner_qq", "user_wechat", "auth_token", "admin_real_name"],
)
def test_forbidden_key_suffixes(key):
    assert is_forbidden_key(key) is True


@pytest.mark.parametrize(
    "key",
    ["connection_id", "room_code", "from_nickname", "reason", "member_count", "capacity", "days_left", "end_at"],
)
def test_documented_payload_keys_are_allowed(key):
    assert is_forbidden_key(key) is False


def test_normalize_key_variants():
    assert normalize_key("User-Email") == "user_email"
    assert normalize_key("  Room Code  ") == "room_code"
    assert normalize_key("userEmail") == "user_email"
    assert normalize_key("roomCode") == "room_code"


def test_camel_case_forbidden_key_is_detected():
    assert is_forbidden_key("userEmail") is True
    assert is_forbidden_key("contactPhone") is True
    assert is_forbidden_key("roomCode") is False


def test_assert_public_payload_allows_none_and_empty():
    assert_public_payload(None)
    assert_public_payload({})


def test_assert_public_payload_rejects_non_object():
    with pytest.raises(PayloadNotPublicError, match="JSON 对象"):
        assert_public_payload(["a"])


def test_assert_public_payload_detects_nested_dict():
    with pytest.raises(PayloadNotPublicError, match="敏感字段"):
        assert_public_payload({"detail": {"email": "alice@example.com"}})


def test_assert_public_payload_detects_dict_in_list():
    with pytest.raises(PayloadNotPublicError, match="敏感字段"):
        assert_public_payload({"members": [{"nickname": "小林"}, {"phone": "138"}]})


def test_assert_public_payload_allows_nested_public_data():
    assert_public_payload(
        {
            "room_code": "100000001",
            "members": [{"nickname": "小林", "member_id": 3}],
            "counts": {"joined": 2, "left": 1},
        }
    )
