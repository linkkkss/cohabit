"""健康探针与管理看板（docs/04 §3.13、§4.7、docs/06 S-01）。"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.db.utils import OperationalError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.adminops.models import Block, Report
from apps.connections.models import ConnectionRequest
from apps.rooms.models import Room

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_user(*, uid: str, email: str, is_staff: bool = False, **extra) -> User:
    values = {
        "uid": uid,
        "email": email,
        "password": "Xk9#mQ2!zR7",
        "nickname": "小满",
        "gender": User.Gender.FEMALE,
        "grade": 2,
        "college": "计算机学院",
        "major": "软件工程",
        "is_staff": is_staff,
    }
    values.update(extra)
    return User.objects.create_user(**values)


def test_health_is_public_and_reports_database_status():
    response = APIClient().get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"status", "version", "db", "time"}
    assert payload["status"] == "ok"
    assert payload["db"] == "ok"
    assert payload["version"] == "0.1.0"
    assert payload["time"]


def test_health_does_not_touch_cache(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("health must not touch the cache")

    for method in ("get", "set", "get_many", "get_or_set"):
        monkeypatch.setattr(cache, method, explode)
    response = APIClient().get("/api/health")
    assert response.status_code == 200


class _BrokenCursor:
    def __enter__(self):
        raise OperationalError("database down")

    def __exit__(self, *args):
        return False


class _BrokenConnections:
    def __getitem__(self, alias):
        return self

    def cursor(self):
        return _BrokenCursor()


def test_health_returns_503_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr("apps.core.views.connections", _BrokenConnections())

    response = APIClient().get("/api/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["db"] == "error"
    assert set(payload) == {"status", "version", "db", "time"}


def test_admin_stats_requires_authentication():
    response = APIClient().get("/api/admin/stats")
    assert response.status_code == 401


def test_admin_stats_rejects_non_staff_users():
    student = make_user(uid="4000000001", email="stats-student@stu.edu.cn")
    client = APIClient()
    client.force_authenticate(user=student)

    response = client.get("/api/admin/stats")

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_admin_stats_returns_counts_for_staff():
    staff = make_user(uid="4000000002", email="stats-staff@stu.edu.cn", is_staff=True)
    other = make_user(uid="4000000003", email="stats-other@stu.edu.cn")
    make_user(uid="4000000004", email="stats-disabled@stu.edu.cn", status=User.Status.DISABLED, is_active=False)
    room = Room.objects.create(
        code="400000001",
        title="测试寝室",
        owner=other,
        capacity=4,
        member_count=1,
        gender=other.gender,
        college=other.college,
        status=Room.Status.DISSOLVED,
    )
    ConnectionRequest.objects.create(
        type=ConnectionRequest.Type.INVITE,
        initiator=other,
        target=staff,
        capacity_pref=2,
        status=ConnectionRequest.Status.PENDING,
    )
    Report.objects.create(
        reporter=other,
        target_type=Report.TargetType.USER,
        target_id=staff.pk,
        reason="测试举报",
    )
    Block.objects.create(blocker=staff, blocked=other)
    client = APIClient()
    client.force_authenticate(user=staff)

    response = client.get("/api/admin/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["users"] == {
        "total": User.objects.count(),
        "active": User.objects.filter(status="ACTIVE", is_active=True).count(),
        "disabled": User.objects.filter(status="DISABLED").count(),
    }
    assert payload["rooms"] == {
        "total": Room.objects.count(),
        "active": Room.objects.filter(status__in=("RECRUITING", "FULL", "LOCKED")).count(),
        "dissolved": Room.objects.filter(status="DISSOLVED").count(),
    }
    assert payload["rooms"]["dissolved"] >= 1
    assert payload["connections"]["open"] >= 1
    assert payload["reports"]["total"] >= 1
    assert payload["reports"]["open"] >= 1
    assert payload["blocks"]["total"] >= 1
    assert payload["generated_at"]
    assert room.status == Room.Status.DISSOLVED


