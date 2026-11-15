"""通知测试共用工厂。"""

from __future__ import annotations

from typing import Any

from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.notifications.models import Notification

PASSWORD = "Xk9#mQ2!zR7"


def make_user(
    *,
    uid: str,
    email: str,
    nickname: str = "小满",
    gender: str = "MALE",
    college: str = "计算机学院",
    major: str = "软件工程",
    grade: int = 2,
) -> User:
    """创建测试用户（10 位 uid + 唯一 email）。"""
    return User.objects.create_user(
        uid=uid,
        email=email,
        password=PASSWORD,
        nickname=nickname,
        gender=gender,
        grade=grade,
        college=college,
        major=major,
    )


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_notification(
    user: User,
    *,
    type: str = Notification.Type.SYSTEM,
    title: str = "测试通知",
    payload: dict[str, Any] | None = None,
    read_at: Any = None,
) -> Notification:
    return Notification.objects.create(
        user=user,
        type=type,
        title=title,
        payload=payload or {},
        read_at=read_at,
    )
