"""connections 测试共用工厂：用户、画像、联系方式、窗口、寝室、请求。"""

from __future__ import annotations

import itertools
from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ContactInfo, User
from apps.adminops.models import Block, TimeWindow
from apps.connections.models import ConnectionRequest
from apps.profiles.models import Profile
from apps.rooms.models import Room, RoomMember

PASSWORD = "Xk9#mQ2!zR7"

_uid_counter = itertools.count(1_100_000_001, 2)
_code_counter = itertools.count()


def next_uid() -> str:
    return str(next(_uid_counter))


def make_user(
    *,
    uid: str | None = None,
    email: str | None = None,
    nickname: str = "小满",
    gender: str = "MALE",
    college: str = "计算机学院",
    major: str = "软件工程",
    grade: int = 2,
    status: str = User.Status.ACTIVE,
) -> User:
    """创建测试用户；未指定 uid/email 时自动生成唯一值。"""
    uid = uid or next_uid()
    email = email or f"u{uid}@example.com"
    user = User.objects.create_user(
        uid=uid,
        email=email,
        password=PASSWORD,
        nickname=nickname,
        gender=gender,
        grade=grade,
        college=college,
        major=major,
    )
    if status != User.Status.ACTIVE:
        User.objects.filter(pk=user.pk).update(status=status)
        user.status = status
    return user


def complete_profile(user: User) -> Profile:
    """直接把画像完整度置 100（服务层只读落库值）。"""
    profile, _ = Profile.objects.update_or_create(
        user=user,
        defaults={"completeness": 100},
    )
    return profile


def incomplete_profile(user: User, *, completeness: int = 60) -> Profile:
    profile, _ = Profile.objects.update_or_create(
        user=user,
        defaults={"completeness": completeness},
    )
    return profile


def make_contact(
    user: User,
    *,
    qq: str | None = "12345678",
    wechat: str | None = "wx_abc",
    phone: str | None = None,
    show_qq: bool = True,
    show_wechat: bool = True,
    show_phone: bool = False,
) -> ContactInfo:
    info, _ = ContactInfo.objects.update_or_create(
        user=user,
        defaults={
            "qq": qq,
            "wechat": wechat,
            "phone": phone,
            "show_qq": show_qq,
            "show_wechat": show_wechat,
            "show_phone": show_phone,
        },
    )
    return info


def pair(
    *,
    completeness: int = 100,
    gender: str = "MALE",
    college: str = "计算机学院",
) -> tuple[User, User]:
    """一对同院同性别的完整画像用户（发起人, 目标）。"""
    first = make_user(gender=gender, college=college)
    second = make_user(gender=gender, college=college, nickname="阿澈")
    if completeness >= 100:
        complete_profile(first)
        complete_profile(second)
    else:
        incomplete_profile(first, completeness=completeness)
        incomplete_profile(second, completeness=completeness)
    return first, second


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def open_window(
    college: str = "计算机学院",
    *,
    starts_in: timedelta = timedelta(hours=-1),
    ends_in: timedelta = timedelta(hours=1),
) -> TimeWindow:
    now = timezone.now()
    window, _ = TimeWindow.objects.update_or_create(
        college=college,
        defaults={"start_at": now + starts_in, "end_at": now + ends_in},
    )
    return window


def next_room_code() -> str:
    return str(900_000_000 + next(_code_counter))


def make_room(
    owner: User,
    *,
    capacity: int = 4,
    status: str = Room.Status.RECRUITING,
    members: tuple[User, ...] = (),
    member_count: int | None = None,
    title: str | None = None,
    college: str | None = None,
    gender: str | None = None,
) -> Room:
    rows = [owner, *members]
    room = Room.objects.create(
        code=next_room_code(),
        title=title if title is not None else f"{owner.nickname}的寝室",
        owner=owner,
        capacity=capacity,
        member_count=member_count if member_count is not None else len(rows),
        gender=gender or owner.gender,
        college=college or owner.college,
        major=owner.major,
        tags=[],
        status=status,
    )
    RoomMember.objects.create(
        room=room,
        user=owner,
        role=RoomMember.Role.OWNER,
        status=RoomMember.Status.ACTIVE,
    )
    for member in members:
        RoomMember.objects.create(
            room=room,
            user=member,
            role=RoomMember.Role.MEMBER,
            status=RoomMember.Status.ACTIVE,
        )
    return room


def make_connection(
    *,
    initiator: User,
    target: User,
    type: str = ConnectionRequest.Type.INVITE,
    room: Room | None = None,
    status: str = ConnectionRequest.Status.PENDING,
    capacity_pref: Any = None,
    expires_in: timedelta = timedelta(hours=12),
    close_reason: str = "",
    message: str = "",
) -> ConnectionRequest:
    """建一条组寝请求；人-人 INVITE 必须带 capacity_pref（check 约束）。"""
    if type == ConnectionRequest.Type.INVITE and room is None and capacity_pref is None:
        capacity_pref = 4
    if not (type == ConnectionRequest.Type.INVITE and room is None):
        capacity_pref = None
    return ConnectionRequest.objects.create(
        type=type,
        initiator=initiator,
        target=target,
        room=room,
        status=status,
        capacity_pref=capacity_pref,
        close_reason=close_reason,
        message=message,
        expires_at=timezone.now() + expires_in,
    )


def block(blocker: User, blocked: User) -> Block:
    return Block.objects.create(blocker=blocker, blocked=blocked)


def error_code(response: Any) -> str:
    try:
        return str(response.json().get("code", ""))
    except Exception:  # noqa: BLE001 - 测试辅助
        return ""


def body(response: Any) -> dict[str, Any]:
    return response.json()
