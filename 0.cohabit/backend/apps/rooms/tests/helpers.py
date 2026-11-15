"""rooms 测试共用工厂：用户、窗口、寝室、请求。"""

from __future__ import annotations

import itertools
from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.adminops.models import TimeWindow
from apps.connections.models import ConnectionRequest
from apps.rooms.models import Room, RoomMember

PASSWORD = "Xk9#mQ2!zR7"

_code_counter = itertools.count()


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


def open_window(
    college: str = "计算机学院",
    *,
    starts_in: timedelta = timedelta(hours=-1),
    ends_in: timedelta = timedelta(hours=1),
) -> TimeWindow:
    """默认开一条“刚刚开、一小时后关”的窗口。"""
    now = timezone.now()
    window, _ = TimeWindow.objects.update_or_create(
        college=college,
        defaults={"start_at": now + starts_in, "end_at": now + ends_in},
    )
    return window


def next_room_code() -> str:
    """固定可预期、不会与随机码冲突的 9 位测试码（900000000+）。"""
    return str(900_000_000 + next(_code_counter))


def make_room(
    owner: User,
    *,
    capacity: int = 4,
    status: str = Room.Status.RECRUITING,
    members: tuple[User, ...] = (),
    code: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    college: str | None = None,
    gender: str | None = None,
    major: str | None = None,
    member_count: int | None = None,
) -> Room:
    """建一间寝室：owner 为 OWNER，``members`` 依次为 MEMBER/ACTIVE。"""
    rows = [owner, *members]
    room = Room.objects.create(
        code=code or next_room_code(),
        title=title if title is not None else f"{owner.nickname}的寝室",
        owner=owner,
        capacity=capacity,
        member_count=member_count if member_count is not None else len(rows),
        gender=gender or owner.gender,
        college=college or owner.college,
        major=major if major is not None else owner.major,
        tags=tags or [],
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


def add_member(
    room: Room,
    user: User,
    *,
    role: str = RoomMember.Role.MEMBER,
    status: str = RoomMember.Status.ACTIVE,
) -> RoomMember:
    return RoomMember.objects.create(room=room, user=user, role=role, status=status)


def make_connection(
    *,
    initiator: User,
    target: User,
    type: str = ConnectionRequest.Type.INVITE,
    room: Room | None = None,
    status: str = ConnectionRequest.Status.PENDING,
    capacity_pref: Any = None,
    expires_in: timedelta = timedelta(hours=12),
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
        message=message,
        expires_at=timezone.now() + expires_in,
    )


def error_code(response: Any) -> str:
    """取错误信封里的 code（缺失返回空串，便于断言失败信息）。"""
    try:
        return str(response.json().get("code", ""))
    except Exception:  # noqa: BLE001 - 测试辅助
        return ""


def body(response: Any) -> dict[str, Any]:
    return response.json()
