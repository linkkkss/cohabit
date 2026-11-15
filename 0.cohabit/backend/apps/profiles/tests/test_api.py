"""画像/问卷/联系方式/公开用户 API 测试（docs/04 §4.1、§4.2）。"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ContactInfo, User
from apps.adminops.models import Block
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.profiles.me_context import _can_apply
from apps.profiles.models import Profile
from apps.rooms.models import Room, RoomMember

from .helpers import full_payload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_user(*, uid: str, email: str, gender: str = "MALE", college: str = "计算机学院", major: str = "软件工程", nickname: str = "小明") -> User:
    user = User.objects.create_user(
        uid=uid,
        email=email,
        password="Xk9#mQ2!zR7",
        nickname=nickname,
        gender=gender,
        grade=2,
        college=college,
        major=major,
    )
    return user


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def complete_profile(client: APIClient) -> None:
    response = client.put("/api/me/profile", full_payload(), format="json")
    assert response.status_code == 200, response.content


def test_registration_creates_profile_and_contact_info():
    user = make_user(uid="0000000001", email="a@stu.edu.cn")
    assert Profile.objects.filter(user=user).exists()
    assert ContactInfo.objects.filter(user=user).exists()

    # 重复保存不重复建（get_or_create 幂等）
    user.save()
    assert Profile.objects.filter(user=user).count() == 1
    assert ContactInfo.objects.filter(user=user).count() == 1

    user.delete()
    assert not Profile.objects.filter(user_id=user.pk).exists()
    assert not ContactInfo.objects.filter(user_id=user.pk).exists()


def test_me_requires_authentication():
    response = APIClient().get("/api/me")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_me_reflects_real_profile_room_and_unread():
    user = make_user(uid="0000000002", email="b@stu.edu.cn")
    client = auth_client(user)

    body = client.get("/api/me").json()
    assert body["profile_completeness"] == 0
    assert body["questionnaire_version"] == "v1"
    assert body["room"] is None
    assert body["unread_count"] == 0

    complete_profile(client)
    Notification.objects.create(user=user, type=Notification.Type.SYSTEM, title="hi")
    body = client.get("/api/me").json()
    assert body["profile_completeness"] == 100
    assert body["unread_count"] == 1
    assert "email" not in body and "contact" not in body


def test_profile_put_and_patch():
    user = make_user(uid="0000000003", email="c@stu.edu.cn")
    client = auth_client(user)

    empty = client.get("/api/me/profile").json()
    assert empty["completeness"] == 0

    complete_profile(client)
    full = client.get("/api/me/profile").json()
    assert full["completeness"] == 100
    assert len(full["dims"]) == 6

    payload = full_payload()
    payload["soft_answers"] = {key: 5 for key in payload["soft_answers"]}
    response = client.patch(
        "/api/me/profile", {"soft_answers": payload["soft_answers"]}, format="json"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["completeness"] == 100
    assert set(body["soft_answers"].values()) == {5}


def test_profile_unknown_key_returns_field_errors():
    user = make_user(uid="0000000004", email="d@stu.edu.cn")
    client = auth_client(user)
    response = client.put(
        "/api/me/profile",
        {**full_payload(), "unknown_key": 1},
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "UNKNOWN_FIELD"
    assert "unknown_key" in body["detail"]["fields"]


def test_questionnaire_requires_login_and_returns_v1():
    assert APIClient().get("/api/questionnaire").status_code == 401

    user = make_user(uid="0000000005", email="e@stu.edu.cn")
    body = auth_client(user).get("/api/questionnaire").json()
    assert body["version"] == "v1"
    assert len(body["hard"]) == 11
    assert len(body["soft"]) == 6
    assert body["tags"] and body["prompts"] and body["red_lines"]


def test_contact_defaults_and_update():
    user = make_user(uid="0000000006", email="f@stu.edu.cn")
    client = auth_client(user)

    body = client.get("/api/me/contact").json()
    assert body == {
        "qq": None,
        "wechat": None,
        "phone": None,
        "show_qq": True,
        "show_wechat": True,
        "show_phone": False,
    }

    response = client.put(
        "/api/me/contact",
        {"qq": "123456789", "wechat": " wx_id ", "phone": "13800138000"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["wechat"] == "wx_id"

    invalid = client.put("/api/me/contact", {"qq": "abc"}, format="json")
    assert invalid.status_code == 400
    assert "qq" in invalid.json()["detail"]["fields"]

    bad_phone = client.put("/api/me/contact", {"phone": "12345"}, format="json")
    assert bad_phone.status_code == 400
    assert "phone" in bad_phone.json()["detail"]["fields"]

    cleared = client.put("/api/me/contact", {"qq": ""}, format="json")
    assert cleared.status_code == 200
    assert cleared.json()["qq"] is None


def test_public_user_hides_private_fields_and_builds_headline():
    viewer = make_user(uid="0000000007", email="g@stu.edu.cn")
    target = make_user(uid="0000000008", email="h@stu.edu.cn", nickname="小红")
    target_client = auth_client(target)
    complete_profile(target_client)

    body = auth_client(viewer).get(f"/api/users/{target.uid}").json()
    assert body["uid"] == target.uid
    assert body["nickname"] == "小红"
    assert body["completeness"] == 100
    assert body["tags"]
    assert body["headline"]
    assert "email" not in body
    assert "contact" not in body
    assert "dims" not in body and "red_lines" not in body


def test_public_user_scope_errors():
    viewer = make_user(uid="0000000009", email="i@stu.edu.cn")
    other_college = make_user(
        uid="0000000010", email="j@stu.edu.cn", college="外国语学院"
    )
    other_gender = make_user(uid="0000000011", email="k@stu.edu.cn", gender="FEMALE")
    blocked = make_user(uid="0000000012", email="l@stu.edu.cn")
    Block.objects.create(blocker=blocked, blocked=viewer)

    client = auth_client(viewer)
    for uid in (other_college.uid, other_gender.uid, "9999999999"):
        response = client.get(f"/api/users/{uid}")
        assert response.status_code == 404
        assert response.json()["code"] == "PROFILE_NOT_FOUND"

    response = client.get(f"/api/users/{blocked.uid}")
    assert response.status_code == 403
    assert response.json()["code"] == "BLOCKED"


def make_room(owner: User, *, code: str = "AB12CD345", capacity: int = 4) -> Room:
    return Room.objects.create(
        code=code,
        title="考研自习寝",
        owner=owner,
        capacity=capacity,
        member_count=1,
        gender=owner.gender,
        college=owner.college,
        major=owner.major,
        tags=["考研"],
        status=Room.Status.RECRUITING,
    )


def test_me_room_summary_reports_cannot_apply():
    owner = make_user(uid="0000000013", email="m@stu.edu.cn")
    room = make_room(owner)
    RoomMember.objects.create(
        room=room, user=owner, role=RoomMember.Role.OWNER, status=RoomMember.Status.ACTIVE
    )

    body = auth_client(owner).get("/api/me").json()
    assert body["room"]["code"] == room.code
    assert body["room"]["my_role"] == "OWNER"
    assert body["room"]["can_apply"] is False
    assert body["room"]["pending_transfer"] is None
    assert body["room"]["owner"]["uid"] == owner.uid
    assert body["room"]["member_preview"][0]["uid"] == owner.uid


def test_can_apply_rules():
    owner = make_user(uid="0000000014", email="n@stu.edu.cn")
    viewer = make_user(uid="0000000015", email="o@stu.edu.cn")
    room = make_room(owner)
    RoomMember.objects.create(
        room=room, user=owner, role=RoomMember.Role.OWNER, status=RoomMember.Status.ACTIVE
    )

    # 非成员、同院同性别、有空位 → 可申请
    assert _can_apply(room, viewer) is True

    # 已有在途申请 → 不可申请
    ConnectionRequest.objects.create(
        type=ConnectionRequest.Type.APPLY,
        initiator=viewer,
        target=owner,
        room=room,
        expires_at=timezone.now() + timezone.timedelta(hours=1),
    )
    assert _can_apply(room, viewer) is False

    # 本人已在该寝 ACTIVE → 不可申请
    assert _can_apply(room, owner) is False

    # 本人已有其他 ACTIVE 寝 → 不可申请
    other_room = make_room(owner, code="ZZ99ZZ999")
    RoomMember.objects.create(
        room=other_room,
        user=viewer,
        role=RoomMember.Role.MEMBER,
        status=RoomMember.Status.ACTIVE,
    )
    assert _can_apply(room, viewer) is False

