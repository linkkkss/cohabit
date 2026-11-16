"""时间窗状态接口（docs/04 §1.8、§3.13、§4.7、P2-1/WK-03）。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.adminops.models import TimeWindow

pytestmark = pytest.mark.django_db

ENDPOINT = "/api/timewindow/"
COLLEGE = "计算机学院"
OTHER_COLLEGE = "外国语学院"
NOW = timezone.make_aware(datetime(2026, 6, 1, 12, 0, 0))
PAYLOAD_FIELDS = {
    "college",
    "status",
    "is_open",
    "start_at",
    "end_at",
    "days_until_start",
    "days_until_end",
    "server_time",
}


class _FrozenClock:
    """把 ``views.timezone`` 替换为固定时刻的时钟，其余能力委托真实 timezone。"""

    def __init__(self, fixed: datetime):
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed

    def __getattr__(self, name):
        return getattr(timezone, name)


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setattr("apps.core.views.timezone", _FrozenClock(NOW))
    return NOW


def make_user(
    *,
    college: str = COLLEGE,
    uid: str = "4100000001",
    email: str = "window@stu.edu.cn",
) -> User:
    return User.objects.create_user(
        uid=uid,
        email=email,
        password="Xk9#mQ2!zR7",
        nickname="小满",
        gender=User.Gender.FEMALE,
        grade=2,
        college=college,
        major="软件工程",
    )


def make_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_window(
    *,
    start_at: datetime,
    end_at: datetime,
    college: str = COLLEGE,
) -> TimeWindow:
    return TimeWindow.objects.create(college=college, start_at=start_at, end_at=end_at)


def test_requires_authentication():
    response = APIClient().get(ENDPOINT)

    assert response.status_code == 401


def test_returns_closed_without_window(frozen_now):
    response = make_client(make_user()).get(ENDPOINT)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == PAYLOAD_FIELDS
    assert payload["college"] == COLLEGE
    assert payload["status"] == "CLOSED"
    assert payload["is_open"] is False
    assert payload["start_at"] is None
    assert payload["end_at"] is None
    assert payload["days_until_start"] is None
    assert payload["days_until_end"] is None
    assert payload["server_time"] == timezone.localtime(frozen_now).isoformat()


def test_ignores_other_college_window(frozen_now):
    make_window(
        start_at=frozen_now - timedelta(days=1),
        end_at=frozen_now + timedelta(days=6),
        college=OTHER_COLLEGE,
    )

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "CLOSED"
    assert payload["is_open"] is False


def test_returns_closed_when_user_has_no_college(frozen_now):
    response = make_client(make_user(college="")).get(ENDPOINT)

    assert response.status_code == 200
    payload = response.json()
    assert payload["college"] == ""
    assert payload["status"] == "CLOSED"
    assert payload["is_open"] is False
    assert payload["days_until_start"] is None
    assert payload["days_until_end"] is None


def test_returns_upcoming_before_start(frozen_now):
    start_at = frozen_now + timedelta(days=10)
    end_at = frozen_now + timedelta(days=20)
    make_window(start_at=start_at, end_at=end_at)

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "UPCOMING"
    assert payload["is_open"] is False
    assert payload["days_until_start"] == 10
    assert payload["days_until_end"] is None
    assert payload["start_at"] == timezone.localtime(start_at).isoformat()
    assert payload["end_at"] == timezone.localtime(end_at).isoformat()


def test_upcoming_rounds_partial_day_up(frozen_now):
    make_window(
        start_at=frozen_now + timedelta(days=9, hours=1),
        end_at=frozen_now + timedelta(days=12),
    )

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "UPCOMING"
    assert payload["days_until_start"] == 10
    assert payload["days_until_end"] is None


def test_returns_open_inside_window(frozen_now):
    start_at = frozen_now - timedelta(days=1)
    end_at = frozen_now + timedelta(days=7)
    make_window(start_at=start_at, end_at=end_at)

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "OPEN"
    assert payload["is_open"] is True
    assert payload["days_until_start"] == 0
    assert payload["days_until_end"] == 7
    assert payload["start_at"] == timezone.localtime(start_at).isoformat()
    assert payload["end_at"] == timezone.localtime(end_at).isoformat()


def test_open_rounds_end_day_up_beyond_seven_days(frozen_now):
    make_window(
        start_at=frozen_now - timedelta(days=1),
        end_at=frozen_now + timedelta(days=7, seconds=1),
    )

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "OPEN"
    assert payload["days_until_end"] == 8


def test_open_at_exact_start_boundary(frozen_now):
    make_window(start_at=frozen_now, end_at=frozen_now + timedelta(days=2))

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "OPEN"
    assert payload["days_until_start"] == 0
    assert payload["days_until_end"] == 2


def test_returns_closed_after_end(frozen_now):
    start_at = frozen_now - timedelta(days=20)
    end_at = frozen_now - timedelta(days=10)
    make_window(start_at=start_at, end_at=end_at)

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "CLOSED"
    assert payload["is_open"] is False
    assert payload["days_until_start"] is None
    assert payload["days_until_end"] is None
    assert payload["start_at"] == timezone.localtime(start_at).isoformat()
    assert payload["end_at"] == timezone.localtime(end_at).isoformat()


def test_closed_at_exact_end_boundary(frozen_now):
    make_window(start_at=frozen_now - timedelta(days=3), end_at=frozen_now)

    payload = make_client(make_user()).get(ENDPOINT).json()

    assert payload["status"] == "CLOSED"
    assert payload["is_open"] is False
    assert payload["days_until_start"] is None
    assert payload["days_until_end"] is None


@pytest.mark.parametrize("path", ["/api/timewindow", "/api/timewindow/"])
def test_trailing_slash_is_optional(frozen_now, path):
    make_window(
        start_at=frozen_now - timedelta(days=1),
        end_at=frozen_now + timedelta(days=3),
    )

    response = make_client(make_user()).get(path)

    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"


def test_serializes_local_timezone_and_iso_format(frozen_now):
    start_at = frozen_now - timedelta(days=1)
    end_at = frozen_now + timedelta(days=7)
    make_window(start_at=start_at, end_at=end_at)

    payload = make_client(make_user()).get(ENDPOINT).json()

    local_offset = timezone.localtime(frozen_now).utcoffset()
    for field in ("start_at", "end_at", "server_time"):
        value = payload[field]
        assert isinstance(value, str)
        assert "T" in value
        parsed = datetime.fromisoformat(value)
        assert parsed.utcoffset() == local_offset
    assert payload["server_time"] == timezone.localtime(frozen_now).isoformat()
    assert payload["start_at"] == timezone.localtime(start_at).isoformat()
    assert payload["end_at"] == timezone.localtime(end_at).isoformat()
