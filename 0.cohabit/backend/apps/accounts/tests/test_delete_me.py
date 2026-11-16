"""DELETE /api/me 与账号禁用级联（docs/04 §4.1、docs/06 S-09/S-10）。"""

from __future__ import annotations

import itertools
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts import lifecycle
from apps.accounts.models import ContactInfo, User
from apps.adminops.models import AuditLog
from apps.connections.models import ConnectionRequest
from apps.notifications.models import Notification
from apps.profiles.models import Profile
from apps.rooms.models import Room, RoomMember

pytestmark = pytest.mark.django_db

PASSWORD = "Xk9#mQ2!zR7"
_UID = itertools.count(200)


def make_user(email: str, *, nickname: str = "小满", **extra) -> User:
    values = {
        "uid": f"{next(_UID):010d}",
        "nickname": nickname,
        "gender": User.Gender.FEMALE,
        "grade": 2,
        "college": "计算机学院",
        "major": "软件工程",
    }
    values.update(extra)
    return User.objects.create_user(email=email, password=PASSWORD, **values)


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_room(owner: User, members: list[User], *, code: str = "123456789", status: str = "RECRUITING") -> Room:
    room = Room.objects.create(
        code=code,
        title="测试寝室",
        owner=owner,
        capacity=4,
        member_count=1 + len(members),
        gender=owner.gender,
        college=owner.college,
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


def make_request(initiator: User, target: User, *, room: Room | None = None) -> ConnectionRequest:
    request_type = ConnectionRequest.Type.APPLY if room is not None else ConnectionRequest.Type.INVITE
    return ConnectionRequest.objects.create(
        type=request_type,
        initiator=initiator,
        target=target,
        room=room,
        capacity_pref=None if room is not None else 4,
        status=ConnectionRequest.Status.PENDING,
        expires_at=timezone.now() + timedelta(days=1),
    )


def test_owner_delete_dissolves_room_and_cascades():
    owner = make_user("owner@stu.edu.cn", nickname="房主")
    member = make_user("member@stu.edu.cn", nickname="成员")
    other = make_user("other@stu.edu.cn", nickname="同学")
    room = make_room(owner, [member], status=Room.Status.FULL)
    request = make_request(other, owner)
    room_request = make_request(member, other, room=room)
    ContactInfo.objects.filter(user=owner).update(
        qq="123456789", wechat="owner-wx", phone="13800138000"
    )
    Profile.objects.filter(user=owner).update(tags=["早睡"])

    response = auth_client(owner).delete("/api/me")

    assert response.status_code == 204
    owner.refresh_from_db()
    room.refresh_from_db()
    request.refresh_from_db()
    room_request.refresh_from_db()
    contact = ContactInfo.objects.get(user=owner)

    assert owner.status == User.Status.DISABLED
    assert owner.is_active is False
    assert owner.email == f"anon{owner.pk}@deleted.local"
    assert (contact.qq, contact.wechat, contact.phone) == (None, None, None)
    assert not (contact.show_qq or contact.show_wechat or contact.show_phone)
    assert room.status == Room.Status.DISSOLVED
    assert room.member_count == 0
    assert room.dissolved_at is not None
    assert set(RoomMember.objects.filter(room=room).values_list("status", flat=True)) == {"LEFT"}
    assert set(RoomMember.objects.filter(room=room).values_list("reason", flat=True)) == {"DISSOLVED"}
    assert request.status == ConnectionRequest.Status.CANCELLED
    assert request.close_reason == ConnectionRequest.CloseReason.USER_DISABLED
    assert request.closed_by_id == owner.pk
    assert room_request.status == ConnectionRequest.Status.CANCELLED
    assert room_request.close_reason == ConnectionRequest.CloseReason.ROOM_DISSOLVED
    assert Profile.objects.filter(user=owner).exists()
    assert Notification.objects.filter(user=member, type=Notification.Type.ROOM_DISSOLVED).exists()
    assert AuditLog.objects.filter(
        action="CONNECTION_CLOSED_DISSOLVED",
        target_type=AuditLog.TargetType.CONNECTION,
        target_id=room_request.pk,
    ).exists()
    assert AuditLog.objects.filter(
        action="USER_DISABLED",
        target_type=AuditLog.TargetType.USER,
        target_id=owner.pk,
        actor_id=owner.pk,
    ).exists()
    assert AuditLog.objects.filter(
        action="CONNECTION_USER_DISABLED",
        target_type=AuditLog.TargetType.CONNECTION,
        target_id=request.pk,
    ).exists()


def test_member_delete_leaves_room_and_keeps_owner():
    owner = make_user("owner2@stu.edu.cn", nickname="房主")
    member = make_user("member2@stu.edu.cn", nickname="成员")
    other = make_user("other2@stu.edu.cn")
    room = make_room(owner, [member], code="123456780", status=Room.Status.FULL)
    request = make_request(member, other)

    response = auth_client(member).delete("/api/me")

    assert response.status_code == 204
    member.refresh_from_db()
    owner.refresh_from_db()
    room.refresh_from_db()
    request.refresh_from_db()
    membership = RoomMember.objects.get(room=room, user=member)
    owner_membership = RoomMember.objects.get(room=room, user=owner)

    assert member.status == User.Status.DISABLED
    assert membership.status == RoomMember.Status.LEFT
    assert membership.reason == RoomMember.Reason.USER_DISABLED
    assert owner_membership.status == RoomMember.Status.ACTIVE
    assert room.status == Room.Status.RECRUITING
    assert room.member_count == 1
    assert request.status == ConnectionRequest.Status.CANCELLED
    assert request.close_reason == ConnectionRequest.CloseReason.USER_DISABLED
    assert Notification.objects.filter(user=owner, type=Notification.Type.MEMBER_LEFT).exists()
    assert AuditLog.objects.filter(action="MEMBER_LEFT", target_type=AuditLog.TargetType.ROOM).exists()


def test_delete_without_room_or_requests_succeeds():
    user = make_user("alone@stu.edu.cn")

    response = auth_client(user).delete("/api/me")

    assert response.status_code == 204
    user.refresh_from_db()
    assert user.status == User.Status.DISABLED
    assert user.is_active is False
    assert user.email == f"anon{user.pk}@deleted.local"


def test_deleted_account_access_and_refresh_tokens_are_rejected():
    user = make_user("tokens@stu.edu.cn")
    access = str(AccessToken.for_user(user))
    refresh = str(RefreshToken.for_user(user))

    assert auth_client(user).delete("/api/me").status_code == 204

    access_client = APIClient()
    access_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    me_response = access_client.get("/api/me")
    assert me_response.status_code in (401, 403)
    assert me_response.json()["code"] == "ACCOUNT_DISABLED"

    refresh_client = APIClient()
    refresh_client.cookies["refresh"] = refresh
    refresh_response = refresh_client.post("/api/auth/refresh")
    assert refresh_response.status_code == 403
    assert refresh_response.json()["code"] == "ACCOUNT_DISABLED"


def test_disable_cascade_rolls_back_when_audit_fails(monkeypatch):
    owner = make_user("rollback-owner@stu.edu.cn", nickname="房主")
    member = make_user("rollback-member@stu.edu.cn", nickname="成员")
    other = make_user("rollback-other@stu.edu.cn")
    room = make_room(owner, [member], code="123456781")
    request = make_request(other, owner)

    def explode(*args, **kwargs):
        raise RuntimeError("audit down")

    monkeypatch.setattr("apps.core.audit.write_audit", explode)

    with pytest.raises(RuntimeError):
        lifecycle.disable_account(owner, actor=owner)

    owner.refresh_from_db()
    room.refresh_from_db()
    request.refresh_from_db()
    assert owner.status == User.Status.ACTIVE
    assert owner.is_active is True
    assert owner.email == "rollback-owner@stu.edu.cn"
    assert room.status == Room.Status.RECRUITING
    assert room.member_count == 2
    assert RoomMember.objects.get(room=room, user=owner).status == RoomMember.Status.ACTIVE
    assert request.status == ConnectionRequest.Status.PENDING


def test_admin_disable_action_uses_same_cascade_and_audits_admin():
    admin = make_user(
        "admin@stu.edu.cn",
        role=User.Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )
    target = make_user("target@stu.edu.cn")
    other = make_user("target-other@stu.edu.cn")
    request = make_request(target, other)

    from django.contrib import admin as django_admin
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.test import RequestFactory

    from apps.accounts.admin import UserAdmin

    http_request = RequestFactory().post("/admin/accounts/user/")
    http_request.user = admin
    http_request.session = {}
    http_request._messages = FallbackStorage(http_request)
    model_admin = UserAdmin(User, django_admin.site)
    model_admin.disable_users(http_request, User.objects.filter(pk=target.pk))

    target.refresh_from_db()
    request.refresh_from_db()
    assert target.status == User.Status.DISABLED
    assert target.is_active is False
    assert request.status == ConnectionRequest.Status.CANCELLED
    assert request.close_reason == ConnectionRequest.CloseReason.USER_DISABLED
    audit = AuditLog.objects.get(action="USER_DISABLED", target_id=target.pk)
    assert audit.actor_id == admin.pk
    assert "disable_users" in model_admin.get_actions(http_request)


def test_delete_me_requires_authentication():
    response = APIClient().delete("/api/me")
    assert response.status_code == 401
