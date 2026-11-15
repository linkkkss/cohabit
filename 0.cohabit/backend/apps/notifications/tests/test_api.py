"""通知 API 契约测试（docs/04 §4.5）。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification

from .helpers import auth_client, make_notification, make_user

pytestmark = pytest.mark.django_db

LIST_URL = "/api/notifications"
UNREAD_COUNT_URL = "/api/notifications/unread-count"
READ_ALL_URL = "/api/notifications/read-all"


@pytest.fixture
def alice():
    return make_user(uid="1000000001", email="alice@example.com", nickname="小满")


@pytest.fixture
def bob():
    return make_user(uid="1000000002", email="bob@example.com", nickname="小林")


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _bulk_notifications(user, count: int, *, prefix: str = "n") -> list[Notification]:
    Notification.objects.bulk_create(
        [
            Notification(
                user=user,
                type=Notification.Type.SYSTEM,
                title=f"{prefix}{index}",
                payload={"reason": "TIMEOUT"},
            )
            for index in range(count)
        ]
    )
    return list(
        Notification.objects.filter(user=user, title__startswith=prefix).order_by("id")
    )


def test_list_requires_auth():
    response = APIClient().get(LIST_URL)

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_REQUIRED"
    assert body["detail"] is None


def test_list_returns_only_own_notifications(alice, bob):
    mine = make_notification(alice, title="我的通知")
    make_notification(bob, title="别人的通知")

    response = auth_client(alice).get(LIST_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert [item["id"] for item in body["results"]] == [mine.pk]
    assert body["results"][0]["title"] == "我的通知"


def test_list_returns_contract_fields(alice):
    notification = make_notification(
        alice,
        type=Notification.Type.CONFIRMED,
        title="组寝成功：100000001",
        payload={"connection_id": 9, "room_code": "100000001"},
    )

    response = auth_client(alice).get(LIST_URL)
    item = response.json()["results"][0]

    assert set(item) == {"id", "type", "title", "payload", "read_at", "created_at"}
    assert item["id"] == notification.pk
    assert item["type"] == Notification.Type.CONFIRMED
    assert item["payload"] == {"connection_id": 9, "room_code": "100000001"}
    assert item["read_at"] is None
    assert _parse_dt(item["created_at"]).tzinfo is not None


def test_list_sorted_by_created_at_desc_then_id_desc(alice):
    oldest = make_notification(alice, title="oldest")
    middle = make_notification(alice, title="middle")
    newest = make_notification(alice, title="newest")
    base = timezone.now()
    Notification.objects.filter(pk=oldest.pk).update(
        created_at=base - timedelta(minutes=2)
    )
    Notification.objects.filter(pk=middle.pk).update(
        created_at=base - timedelta(minutes=1)
    )
    Notification.objects.filter(pk=newest.pk).update(created_at=base)

    response = auth_client(alice).get(LIST_URL)

    ids = [item["id"] for item in response.json()["results"]]
    assert ids == [newest.pk, middle.pk, oldest.pk]


def test_list_ties_on_created_at_use_id_desc(alice):
    first = make_notification(alice, title="first")
    second = make_notification(alice, title="second")
    same_moment = timezone.now()
    Notification.objects.filter(pk__in=[first.pk, second.pk]).update(
        created_at=same_moment
    )

    response = auth_client(alice).get(LIST_URL)

    ids = [item["id"] for item in response.json()["results"]]
    assert ids == [second.pk, first.pk]


def test_list_default_page_size_is_20(alice):
    _bulk_notifications(alice, 25)

    response = auth_client(alice).get(LIST_URL)

    body = response.json()
    assert body["count"] == 25
    assert len(body["results"]) == 20
    assert body["previous"] is None
    assert body["next"] is not None


def test_list_second_page(alice):
    _bulk_notifications(alice, 25)

    body = auth_client(alice).get(LIST_URL, {"page": 2}).json()

    assert body["count"] == 25
    assert len(body["results"]) == 5
    assert body["previous"] is not None


def test_list_page_size_capped_at_50(alice):
    _bulk_notifications(alice, 60)

    body = auth_client(alice).get(LIST_URL, {"page_size": 100}).json()

    assert body["count"] == 60
    assert len(body["results"]) == 50


def test_list_unread_filter(alice):
    unread_one = make_notification(alice, title="unread-1")
    make_notification(alice, title="unread-2")
    read_one = make_notification(alice, title="read-1")
    Notification.objects.filter(pk=read_one.pk).update(read_at=timezone.now())
    assert unread_one.read_at is None

    client = auth_client(alice)
    for value in ("true", "1", "TRUE", "yes"):
        body = client.get(LIST_URL, {"unread": value}).json()
        assert body["count"] == 2, value

    body = client.get(LIST_URL, {"unread": "false"}).json()
    assert body["count"] == 3


def test_unread_count_only_own(alice, bob):
    make_notification(alice)
    make_notification(alice)
    read = make_notification(alice)
    Notification.objects.filter(pk=read.pk).update(read_at=timezone.now())
    make_notification(bob)

    response = auth_client(alice).get(UNREAD_COUNT_URL)

    assert response.status_code == 200
    assert response.json() == {"count": 2}


def test_unread_count_requires_auth():
    assert APIClient().get(UNREAD_COUNT_URL).status_code == 401


def test_read_marks_notification_and_is_idempotent(alice):
    notification = make_notification(alice)
    client = auth_client(alice)
    url = f"{LIST_URL}/{notification.pk}/read"

    first = client.post(url)
    assert first.status_code == 200
    first_read_at = first.json()["read_at"]
    assert first_read_at is not None

    second = client.post(url)
    assert second.status_code == 200
    assert second.json()["read_at"] == first_read_at

    notification.refresh_from_db()
    assert notification.read_at is not None
    assert notification.read_at == _parse_dt(first_read_at)


def test_read_unknown_notification_returns_404(alice):
    response = auth_client(alice).post(f"{LIST_URL}/999999/read")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOTIFICATION_NOT_FOUND"
    assert body["detail"] is None


def test_read_other_users_notification_returns_404(alice, bob):
    notification = make_notification(bob)

    response = auth_client(alice).post(f"{LIST_URL}/{notification.pk}/read")

    assert response.status_code == 404
    assert response.json()["code"] == "NOTIFICATION_NOT_FOUND"
    notification.refresh_from_db()
    assert notification.read_at is None


def test_read_own_notification_after_other_user_attempt(alice, bob):
    notification = make_notification(bob)
    auth_client(alice).post(f"{LIST_URL}/{notification.pk}/read")

    response = auth_client(bob).post(f"{LIST_URL}/{notification.pk}/read")

    assert response.status_code == 200
    assert response.json()["read_at"] is not None


def test_read_all_marks_only_own_and_is_idempotent(alice, bob):
    make_notification(alice)
    make_notification(alice)
    read = make_notification(alice)
    Notification.objects.filter(pk=read.pk).update(read_at=timezone.now())
    make_notification(bob)
    client = auth_client(alice)

    first = client.post(READ_ALL_URL)
    assert first.status_code == 200
    assert first.json() == {"updated": 2}

    second = client.post(READ_ALL_URL)
    assert second.status_code == 200
    assert second.json() == {"updated": 0}

    assert Notification.objects.filter(user=alice, read_at__isnull=True).count() == 0
    assert Notification.objects.filter(user=bob, read_at__isnull=True).count() == 1


def test_read_all_requires_auth():
    response = APIClient().post(READ_ALL_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_trailing_slash_is_accepted(alice):
    notification = make_notification(alice)
    client = auth_client(alice)

    assert client.get(f"{LIST_URL}/").status_code == 200
    assert client.get(f"{UNREAD_COUNT_URL}/").json() == {"count": 1}
    assert client.post(f"{LIST_URL}/{notification.pk}/read/").status_code == 200
    assert client.post(f"{READ_ALL_URL}/").json() == {"updated": 0}
