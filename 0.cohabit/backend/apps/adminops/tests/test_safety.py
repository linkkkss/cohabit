"""举报 / 拉黑 API 与副作用（docs/04 §4.6、docs/06 S-07/S-08/S-14/W-04）。

覆盖：举报字段/长度/枚举/日限频/重复举报/未登录；拉黑幂等、自拉黑、未知 uid、
在途请求关闭为 ``CANCELLED/BLOCKED``（含通知与审计）、已成立寝室保留、
双向不可见（匹配 / 资料 / 广场）与权限矩阵。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.serializers import avatar_key_for
from apps.adminops.models import AuditLog, Block, Report
from apps.connections.models import OPEN_STATUSES, ConnectionRequest
from apps.connections.tests.helpers import (
    auth_client,
    make_connection,
    make_room,
    make_user,
    open_window,
)
from apps.notifications.models import Notification
from apps.profiles.services import save_profile
from apps.profiles.tests.helpers import full_payload, full_tags
from apps.rooms.models import Room, RoomMember

pytestmark = pytest.mark.django_db

REPORTS_URL = "/api/reports"
BLOCKS_URL = "/api/blocks"


def complete(user: User) -> None:
    """画像置 100：匹配候选池/资料可见性都要求完整画像。"""
    payload = full_payload()
    payload["tags"] = full_tags()
    save_profile(user, payload)


def report_payload(*, target_type: str = "USER", target_id: int, reason: str = "骚扰"):
    return {"target_type": target_type, "target_id": target_id, "reason": reason}


@pytest.fixture
def me() -> User:
    return make_user(nickname="我")


@pytest.fixture
def other() -> User:
    return make_user(nickname="对方")


# --------------------------------------------------------------------------- #
# 举报：POST /api/reports
# --------------------------------------------------------------------------- #
def test_create_report_returns_201_report_payload(me, other):
    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_id=other.pk, reason="在群里骚扰我"),
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {
        "id",
        "target_type",
        "target_id",
        "reason",
        "status",
        "handled_by",
        "created_at",
    }
    assert payload["target_type"] == "USER"
    assert payload["target_id"] == other.pk
    assert payload["reason"] == "在群里骚扰我"
    assert payload["status"] == Report.Status.OPEN
    assert payload["handled_by"] is None
    created_at = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
    assert created_at.tzinfo is not None

    row = Report.objects.get(pk=payload["id"])
    assert row.reporter_id == me.pk
    assert row.target_type == Report.TargetType.USER
    assert row.target_id == other.pk


@pytest.mark.parametrize("target_type", ["USER", "ROOM", "CONNECTION"])
def test_create_report_accepts_each_target_type(me, target_type):
    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_type=target_type, target_id=7),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["target_type"] == target_type
    assert Report.objects.get().target_type == target_type


def test_create_report_rejects_unknown_target_type(me):
    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_type="CHATBOT", target_id=7),
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "target_type" in response.json()["detail"]["fields"]
    assert not Report.objects.exists()


@pytest.mark.parametrize("reason", ["", "   ", "字" * 201])
def test_create_report_rejects_bad_reason(me, other, reason):
    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_id=other.pk, reason=reason),
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "reason" in response.json()["detail"]["fields"]
    assert not Report.objects.exists()


def test_create_report_accepts_200_chars_and_trims_reason(me, other):
    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_id=other.pk, reason=f"  {'字' * 200}  "),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["reason"] == "字" * 200
    assert Report.objects.get().reason == "字" * 200


@pytest.mark.parametrize("target_id", [0, -1, "abc", None])
def test_create_report_rejects_bad_target_id(me, target_id):
    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_id=target_id),
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "target_id" in response.json()["detail"]["fields"]


def test_create_report_does_not_validate_target_existence(me):
    """举报只落库给 Admin 人工处理（docs/03 §1.8.2：目标不建外键）。"""
    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_type="ROOM", target_id=999_999_999, reason="虚假寝室"),
        format="json",
    )

    assert response.status_code == 201
    assert Report.objects.count() == 1


def test_create_report_requires_login(other):
    response = APIClient().post(
        REPORTS_URL,
        report_payload(target_id=other.pk),
        format="json",
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
    assert not Report.objects.exists()


def test_repeated_reports_on_same_target_are_allowed(me, other):
    client = auth_client(me)
    for _ in range(3):
        response = client.post(
            REPORTS_URL,
            report_payload(target_id=other.pk),
            format="json",
        )
        assert response.status_code == 201
    assert Report.objects.filter(reporter=me, target_id=other.pk).count() == 3


def test_report_daily_limit_returns_429_with_retry_after(me, other):
    client = auth_client(me)
    for _ in range(10):
        response = client.post(
            REPORTS_URL,
            report_payload(target_id=other.pk),
            format="json",
        )
        assert response.status_code == 201

    limited = client.post(
        REPORTS_URL,
        report_payload(target_id=other.pk),
        format="json",
    )

    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"
    retry_after = int(limited["Retry-After"])
    assert 1 <= retry_after <= 24 * 60 * 60
    assert Report.objects.filter(reporter=me).count() == 10

    # 限频按人计算：其他人不受影响。
    assert (
        auth_client(make_user())
        .post(REPORTS_URL, report_payload(target_id=other.pk), format="json")
        .status_code
        == 201
    )


def test_report_daily_limit_resets_next_day(me, other):
    for _ in range(10):
        Report.objects.create(
            reporter=me,
            target_type=Report.TargetType.USER,
            target_id=other.pk,
            reason="昨天的举报",
        )
    Report.objects.filter(reporter=me).update(
        created_at=timezone.now() - timedelta(days=1),
    )

    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_id=other.pk),
        format="json",
    )

    assert response.status_code == 201
    assert Report.objects.filter(reporter=me).count() == 11


def test_create_report_does_not_ban_or_notify(me, other):
    """只落 Report：不自动封禁、不通知被举报人、不写审计（docs/04 §4.6）。"""
    auth_client(me).post(REPORTS_URL, report_payload(target_id=other.pk), format="json")

    other.refresh_from_db()
    assert other.status == User.Status.ACTIVE
    assert Report.objects.get().status == Report.Status.OPEN
    assert not Notification.objects.exists()
    assert not AuditLog.objects.exists()


def test_create_report_ignores_time_window(me, other):
    """举报不受时间窗限制（docs/04 §1.8、docs/06 W-04）。"""
    open_window(
        me.college,
        starts_in=timedelta(hours=-5),
        ends_in=timedelta(hours=-1),
    )

    response = auth_client(me).post(
        REPORTS_URL,
        report_payload(target_id=other.pk),
        format="json",
    )

    assert response.status_code == 201


def test_reports_endpoint_has_no_list(me):
    """v1 不提供学生端举报列表（docs/03 §1.8.2）。"""
    response = auth_client(me).get(REPORTS_URL)

    assert response.status_code == 405
    assert not Report.objects.exists()


# --------------------------------------------------------------------------- #
# 拉黑：/api/blocks
# --------------------------------------------------------------------------- #
def test_blocks_require_login():
    client = APIClient()

    list_response = client.get(BLOCKS_URL)
    post_response = client.post(BLOCKS_URL, {"uid": "1100000001"}, format="json")
    delete_response = client.delete(f"{BLOCKS_URL}/1100000001")

    for response in (list_response, post_response, delete_response):
        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_REQUIRED"
    assert not Block.objects.exists()


def test_list_blocks_empty(me):
    response = auth_client(me).get(BLOCKS_URL)

    assert response.status_code == 200
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


def test_list_blocks_returns_public_fields_only(me, other):
    Block.objects.create(blocker=me, blocked=other)

    payload = auth_client(me).get(BLOCKS_URL).json()

    assert payload["count"] == 1
    item = payload["results"][0]
    assert set(item) == {"uid", "nickname", "avatar_key", "created_at"}
    assert item["uid"] == other.uid
    assert item["nickname"] == other.nickname
    assert item["avatar_key"] == avatar_key_for(other.uid)
    created_at = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
    assert created_at.tzinfo is not None
    assert not {"email", "qq", "wechat", "phone", "contact"} & set(item)


def test_list_blocks_only_mine_and_newest_first(me, other):
    first = Block.objects.create(blocker=me, blocked=make_user(nickname="甲"))
    second = Block.objects.create(blocker=me, blocked=make_user(nickname="乙"))
    Block.objects.create(blocker=make_user(nickname="丙"), blocked=other)

    payload = auth_client(me).get(BLOCKS_URL).json()

    assert payload["count"] == 2
    assert [item["uid"] for item in payload["results"]] == [
        second.blocked.uid,
        first.blocked.uid,
    ]


def test_list_blocks_paginates(me):
    for _ in range(3):
        Block.objects.create(blocker=me, blocked=make_user())

    payload = auth_client(me).get(BLOCKS_URL, {"page_size": 2}).json()

    assert payload["count"] == 3
    assert len(payload["results"]) == 2
    assert payload["next"] is not None


def test_block_user_returns_204_and_creates_row(me, other):
    response = auth_client(me).post(BLOCKS_URL, {"uid": other.uid}, format="json")

    assert response.status_code == 204
    assert response.content == b""
    row = Block.objects.get()
    assert row.blocker_id == me.pk
    assert row.blocked_id == other.pk


def test_block_user_is_idempotent(me, other):
    request_row = make_connection(initiator=me, target=other)
    client = auth_client(me)

    assert client.post(BLOCKS_URL, {"uid": other.uid}, format="json").status_code == 204
    notifications = Notification.objects.count()
    audits = AuditLog.objects.count()

    again = client.post(BLOCKS_URL, {"uid": other.uid}, format="json")

    assert again.status_code == 204
    assert Block.objects.count() == 1
    assert Notification.objects.count() == notifications == 2
    assert AuditLog.objects.count() == audits == 1
    request_row.refresh_from_db()
    assert request_row.status == ConnectionRequest.Status.CANCELLED


def test_block_self_returns_400(me):
    response = auth_client(me).post(BLOCKS_URL, {"uid": me.uid}, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "SELF_REQUEST"
    assert not Block.objects.exists()


def test_block_unknown_uid_returns_404(me):
    response = auth_client(me).post(BLOCKS_URL, {"uid": "0000000000"}, format="json")

    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"
    assert not Block.objects.exists()


def test_block_disabled_user_returns_404(me):
    disabled = make_user(status=User.Status.DISABLED)

    response = auth_client(me).post(BLOCKS_URL, {"uid": disabled.uid}, format="json")

    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"
    assert not Block.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [{"uid": "123"}, {"uid": ""}, {}, {"uid": "abcdefghij"}],
)
def test_block_rejects_malformed_uid(me, payload):
    response = auth_client(me).post(BLOCKS_URL, payload, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "uid" in response.json()["detail"]["fields"]
    assert not Block.objects.exists()


def test_unblock_is_idempotent(me, other):
    Block.objects.create(blocker=me, blocked=other)
    client = auth_client(me)

    assert client.delete(f"{BLOCKS_URL}/{other.uid}").status_code == 204
    assert not Block.objects.exists()
    assert client.delete(f"{BLOCKS_URL}/{other.uid}").status_code == 204


def test_unblock_unknown_uid_returns_204(me):
    assert auth_client(me).delete(f"{BLOCKS_URL}/0000000000").status_code == 204


def test_unblock_malformed_uid_returns_400(me):
    response = auth_client(me).delete(f"{BLOCKS_URL}/123")

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "uid" in response.json()["detail"]["fields"]


def test_unblock_only_removes_my_direction(me, other):
    Block.objects.create(blocker=me, blocked=other)
    Block.objects.create(blocker=other, blocked=me)

    auth_client(me).delete(f"{BLOCKS_URL}/{other.uid}")

    assert not Block.objects.filter(blocker=me).exists()
    assert Block.objects.filter(blocker=other, blocked=me).exists()


def test_safety_routes_accept_trailing_slash(me, other):
    client = auth_client(me)

    assert (
        client.post(
            f"{REPORTS_URL}/",
            report_payload(target_id=other.pk),
            format="json",
        ).status_code
        == 201
    )
    assert client.post(f"{BLOCKS_URL}/", {"uid": other.uid}, format="json").status_code == 204
    assert client.get(f"{BLOCKS_URL}/").json()["count"] == 1
    assert client.delete(f"{BLOCKS_URL}/{other.uid}/").status_code == 204


# --------------------------------------------------------------------------- #
# 拉黑副作用：关闭双方在途请求（S-07）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("status", OPEN_STATUSES)
def test_block_closes_open_request_as_blocked(me, other, status):
    request_row = make_connection(initiator=me, target=other, status=status)
    version_before = request_row.version

    response = auth_client(me).post(BLOCKS_URL, {"uid": other.uid}, format="json")

    assert response.status_code == 204
    request_row.refresh_from_db()
    assert request_row.status == ConnectionRequest.Status.CANCELLED
    assert request_row.close_reason == ConnectionRequest.CloseReason.BLOCKED
    assert request_row.closed_by_id == me.pk
    assert request_row.version == version_before + 1


def test_block_closes_requests_in_both_directions(me, other):
    outgoing = make_connection(initiator=me, target=other)
    incoming = make_connection(
        initiator=other,
        target=me,
        status=ConnectionRequest.Status.CONTACT_SHARED,
    )

    auth_client(me).post(BLOCKS_URL, {"uid": other.uid}, format="json")

    for row in (outgoing, incoming):
        row.refresh_from_db()
        assert row.status == ConnectionRequest.Status.CANCELLED
        assert row.close_reason == ConnectionRequest.CloseReason.BLOCKED
        assert row.closed_by_id == me.pk
    assert AuditLog.objects.filter(action="CONNECTION_BLOCKED").count() == 2
    assert Notification.objects.count() == 4


def test_block_notifies_both_parties_and_writes_audit(me, other):
    request_row = make_connection(initiator=other, target=me)

    auth_client(me).post(BLOCKS_URL, {"uid": other.uid}, format="json")

    notifications = Notification.objects.filter(type=Notification.Type.SYSTEM)
    assert set(notifications.values_list("user_id", flat=True)) == {me.pk, other.pk}
    for notification in notifications:
        assert notification.title == "请求已关闭"
        assert notification.payload == {
            "connection_id": request_row.pk,
            "reason": "BLOCKED",
        }

    audit = AuditLog.objects.get()
    assert audit.action == "CONNECTION_BLOCKED"
    assert audit.target_type == AuditLog.TargetType.CONNECTION
    assert audit.target_id == request_row.pk
    assert audit.actor_id == me.pk
    assert audit.meta == {
        "blocker_id": me.pk,
        "blocked_id": other.pk,
        "reason": "BLOCKED",
    }


def test_block_room_invite_notification_carries_room_code(me, other):
    room = make_room(other)
    request_row = make_connection(initiator=other, target=me, room=room)

    auth_client(me).post(BLOCKS_URL, {"uid": other.uid}, format="json")

    payloads = [notification.payload for notification in Notification.objects.all()]
    assert len(payloads) == 2
    for payload in payloads:
        assert payload == {
            "connection_id": request_row.pk,
            "reason": "BLOCKED",
            "room_code": room.code,
        }


def test_block_keeps_confirmed_room(me, other):
    """已成立寝室不自动解散（docs/02 X-30、docs/06 S-08）。"""
    room = make_room(me, members=(other,))
    confirmed = make_connection(
        initiator=me,
        target=other,
        room=room,
        status=ConnectionRequest.Status.CONFIRMED,
    )

    response = auth_client(me).post(BLOCKS_URL, {"uid": other.uid}, format="json")

    assert response.status_code == 204
    confirmed.refresh_from_db()
    assert confirmed.status == ConnectionRequest.Status.CONFIRMED
    assert confirmed.close_reason == ""
    room.refresh_from_db()
    assert room.status == Room.Status.RECRUITING
    assert room.member_count == 2
    assert (
        RoomMember.objects.filter(
            room=room,
            status=RoomMember.Status.ACTIVE,
        ).count()
        == 2
    )
    assert not Notification.objects.exists()
    assert not AuditLog.objects.exists()


def test_block_leaves_terminal_requests_untouched(me, other):
    cancelled = make_connection(
        initiator=me,
        target=other,
        status=ConnectionRequest.Status.CANCELLED,
        close_reason=ConnectionRequest.CloseReason.INITIATOR_CANCEL,
    )

    auth_client(me).post(BLOCKS_URL, {"uid": other.uid}, format="json")

    cancelled.refresh_from_db()
    assert cancelled.status == ConnectionRequest.Status.CANCELLED
    assert cancelled.close_reason == ConnectionRequest.CloseReason.INITIATOR_CANCEL
    assert not Notification.objects.exists()
    assert not AuditLog.objects.exists()


def test_unblock_does_not_reopen_closed_requests(me, other):
    request_row = make_connection(initiator=me, target=other)
    client = auth_client(me)

    client.post(BLOCKS_URL, {"uid": other.uid}, format="json")
    client.delete(f"{BLOCKS_URL}/{other.uid}")

    request_row.refresh_from_db()
    assert request_row.status == ConnectionRequest.Status.CANCELLED
    assert request_row.close_reason == ConnectionRequest.CloseReason.BLOCKED


# --------------------------------------------------------------------------- #
# 拉黑副作用：双向不可见（S-07）
# --------------------------------------------------------------------------- #
def test_block_hides_match_candidates_both_ways(me, other):
    complete(me)
    complete(other)
    client = auth_client(me)
    assert client.get("/api/match").json()["count"] == 1

    client.post(BLOCKS_URL, {"uid": other.uid}, format="json")

    assert client.get("/api/match").json()["count"] == 0
    assert auth_client(other).get("/api/match").json()["count"] == 0


def test_block_hides_profile_and_match_detail_both_ways(me, other):
    complete(me)
    complete(other)
    client = auth_client(me)
    assert client.get(f"/api/users/{other.uid}").status_code == 200

    client.post(BLOCKS_URL, {"uid": other.uid}, format="json")

    for viewer, target in ((client, other), (auth_client(other), me)):
        profile = viewer.get(f"/api/users/{target.uid}")
        assert profile.status_code == 403
        assert profile.json()["code"] == "BLOCKED"

        detail = viewer.get(f"/api/match/{target.uid}")
        assert detail.status_code == 403
        assert detail.json()["code"] == "BLOCKED"


def test_block_hides_room_square_both_ways(me, other):
    make_room(me, members=(other,))
    stranger = make_user(nickname="路人")
    client = auth_client(stranger)
    assert client.get("/api/rooms").json()["count"] == 1

    # 房主拉黑旁观者
    assert auth_client(me).post(BLOCKS_URL, {"uid": stranger.uid}, format="json").status_code == 204
    assert client.get("/api/rooms").json()["count"] == 0

    # 反向：旁观者拉黑房主
    auth_client(me).delete(f"{BLOCKS_URL}/{stranger.uid}")
    assert client.post(BLOCKS_URL, {"uid": me.uid}, format="json").status_code == 204
    assert client.get("/api/rooms").json()["count"] == 0
