"""``notify`` / ``build_title`` 单元测试（docs/03 §9、docs/02 §8）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.adminops.models import TimeWindow
from apps.core.privacy import PayloadNotPublicError
from apps.notifications.models import Notification
from apps.notifications.services import (
    SYSTEM_FALLBACK_TITLE,
    SYSTEM_TITLES,
    TITLE_MAX_LENGTH,
    TITLE_TEMPLATES,
    build_title,
    normalize_type,
    notify,
)

from .helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return make_user(uid="1000000001", email="alice@example.com", nickname="小满")


def test_notify_creates_notification_in_caller_transaction(user):
    notification = notify(
        user,
        Notification.Type.CONNECTION_RECEIVED,
        {"connection_id": 7, "from_nickname": "小林", "request_type": "INVITE"},
    )

    assert notification.pk is not None
    assert notification.user_id == user.pk
    assert notification.type == Notification.Type.CONNECTION_RECEIVED
    assert notification.title == "小林 想和你组寝"
    assert notification.payload == {
        "connection_id": 7,
        "from_nickname": "小林",
        "request_type": "INVITE",
    }
    assert notification.read_at is None
    assert notification.created_at is not None
    assert Notification.objects.filter(user=user).count() == 1


@pytest.mark.parametrize(
    ("notification_type", "payload", "expected"),
    [
        (
            Notification.Type.CONNECTION_RECEIVED,
            {"from_nickname": "小林"},
            "小林 想和你组寝",
        ),
        (Notification.Type.CONTACT_SHARED, {}, "可以交换联系方式了"),
        (
            Notification.Type.CONFIRM_PENDING,
            {"nickname": "小林"},
            "小林 已确认，等你确认",
        ),
        (
            Notification.Type.CONFIRMED,
            {"room_code": "100000001"},
            "组寝成功：100000001",
        ),
        (Notification.Type.DECLINED, {"from_nickname": "小周"}, "小周 拒绝了请求"),
        (
            Notification.Type.MEMBER_JOINED,
            {"nickname": "小周", "room_code": "100000002"},
            "小周 加入了 100000002",
        ),
        (
            Notification.Type.ROOM_FULL,
            {"room_code": "100000003"},
            "100000003 已满员",
        ),
        (
            Notification.Type.MEMBER_LEFT,
            {"nickname": "小周", "room_code": "100000002"},
            "小周 退出了 100000002",
        ),
        (
            Notification.Type.ROOM_LOCKED,
            {"room_code": "100000004"},
            "100000004 已锁定",
        ),
        (
            Notification.Type.ROOM_DISSOLVED,
            {"room_code": "100000006"},
            "100000006 已解散",
        ),
        (
            Notification.Type.ROOM_ARCHIVED,
            {"room_code": "100000005"},
            "100000005 已归档",
        ),
        (
            Notification.Type.TRANSFER_RECEIVED,
            {"from_nickname": "小林"},
            "小林 想转让房主",
        ),
        (Notification.Type.TRANSFER_ACCEPTED, {}, "房主转让成功"),
        (Notification.Type.TRANSFER_DECLINED, {}, "房主转让被拒绝"),
        (Notification.Type.TRANSFER_EXPIRED, {}, "房主转让已过期"),
        (Notification.Type.TRANSFER_CANCELLED, {}, "房主转让已取消"),
        (
            Notification.Type.WINDOW_CLOSING,
            {"days_left": 3},
            "组寝窗口还有 3 天关闭",
        ),
    ],
)
def test_build_title_templates(notification_type, payload, expected):
    assert build_title(notification_type, payload) == expected


@pytest.mark.parametrize(("reason", "expected"), sorted(SYSTEM_TITLES.items()))
def test_build_title_system_reasons(reason, expected):
    assert build_title(Notification.Type.SYSTEM, {"reason": reason}) == expected


def test_build_title_system_reason_is_case_insensitive():
    assert build_title(Notification.Type.SYSTEM, {"reason": "timeout"}) == "请求已过期"


def test_build_title_system_unknown_reason_falls_back():
    assert (
        build_title(Notification.Type.SYSTEM, {"reason": "NOT_A_REASON"})
        == SYSTEM_FALLBACK_TITLE
    )


def test_build_title_falls_back_to_generic_placeholders():
    assert build_title(Notification.Type.MEMBER_JOINED, {}) == "对方 加入了 寝室"
    assert build_title(Notification.Type.CONFIRMED, {}) == "组寝成功：寝室"


def test_title_templates_cover_all_non_system_types():
    expected = set(Notification.Type.values) - {Notification.Type.SYSTEM}
    assert set(TITLE_TEMPLATES) == expected


def test_notify_accepts_lowercase_type(user):
    notification = notify(user, "member_joined", {"nickname": "小周", "room_code": "100000002"})
    assert notification.type == Notification.Type.MEMBER_JOINED


def test_notify_rejects_unknown_type(user):
    with pytest.raises(ValueError, match="未知的通知类型"):
        notify(user, "NOT_A_TYPE", {})
    assert Notification.objects.count() == 0


def test_normalize_type_accepts_enum_member():
    assert normalize_type(Notification.Type.SYSTEM) == "SYSTEM"


def test_notify_explicit_title_wins(user):
    notification = notify(user, Notification.Type.SYSTEM, {"reason": "TIMEOUT"}, "自定义标题")
    assert notification.title == "自定义标题"


def test_notify_truncates_title_to_model_limit(user):
    notification = notify(user, Notification.Type.SYSTEM, {}, "长" * 80)
    assert len(notification.title) == TITLE_MAX_LENGTH
    assert notification.title == "长" * TITLE_MAX_LENGTH


def test_build_title_truncates_long_nickname():
    title = build_title(
        Notification.Type.CONNECTION_RECEIVED,
        {"from_nickname": "昵" * 80},
    )
    assert len(title) <= TITLE_MAX_LENGTH


@pytest.mark.parametrize(
    "key",
    [
        "email",
        "qq",
        "wechat",
        "phone",
        "token",
        "real_name",
        "contact_info",
        "user_email",
        "refresh_token",
    ],
)
def test_notify_rejects_forbidden_payload_keys(user, key):
    with pytest.raises(PayloadNotPublicError):
        notify(user, Notification.Type.SYSTEM, {key: "sensitive-value"})
    assert Notification.objects.count() == 0


def test_notify_rejects_nested_forbidden_payload_key(user):
    with pytest.raises(PayloadNotPublicError):
        notify(
            user,
            Notification.Type.SYSTEM,
            {"detail": {"contact_phone": "13800000000"}},
        )
    assert Notification.objects.count() == 0


def test_notify_rejects_non_object_payload(user):
    with pytest.raises(ValueError, match="payload"):
        notify(user, Notification.Type.SYSTEM, ["not", "an", "object"])


def test_notify_allows_documented_payload_keys(user):
    payload = {
        "connection_id": 12,
        "room_code": "100000001",
        "from_nickname": "小林",
        "reason": "FULL",
        "member_count": 3,
        "capacity": 4,
        "days_left": 3,
        "end_at": "2026-12-01T00:00:00+00:00",
    }
    notification = notify(user, Notification.Type.SYSTEM, payload)
    assert notification.payload == payload


def test_notify_accepts_user_id(user):
    notification = notify(user.pk, Notification.Type.SYSTEM, {"reason": "TIMEOUT"})
    assert notification.user_id == user.pk


def test_notify_payload_is_copied(user):
    payload = {"reason": "TIMEOUT"}
    notification = notify(user, Notification.Type.SYSTEM, payload)
    payload["reason"] = "MUTATED"
    assert notification.payload == {"reason": "TIMEOUT"}


def test_notify_rolls_back_with_caller_transaction(user):
    """通知与业务同事务：业务异常时通知一并回滚（docs/06 S-11）。"""
    college = "计算机学院"
    end_at = timezone.now() + timedelta(days=30)

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            TimeWindow.objects.create(
                college=college,
                start_at=timezone.now() - timedelta(days=1),
                end_at=end_at,
            )
            notify(user, Notification.Type.SYSTEM, {"reason": "TIMEOUT"})
            raise RuntimeError("business failed")

    assert TimeWindow.objects.filter(college=college).count() == 0
    assert Notification.objects.count() == 0
