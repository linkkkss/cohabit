"""``is_window_open`` / ``require_window_open`` 单元测试（docs/02 §7）。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.adminops.models import TimeWindow
from apps.core.timewindow import (
    WindowClosed,
    get_open_window,
    is_window_open,
    require_window_open,
)

pytestmark = pytest.mark.django_db

COLLEGE = "计算机学院"
OTHER_COLLEGE = "外国语学院"
BASE = timezone.make_aware(datetime(2026, 6, 1, 12, 0, 0))


def make_window(*, start_at: datetime, end_at: datetime, college: str = COLLEGE) -> TimeWindow:
    return TimeWindow.objects.create(college=college, start_at=start_at, end_at=end_at)


def test_no_window_means_closed():
    assert is_window_open(COLLEGE) is False
    assert get_open_window(COLLEGE) is None


def test_window_of_other_college_does_not_open():
    make_window(start_at=BASE - timedelta(hours=1), end_at=BASE + timedelta(hours=1), college=OTHER_COLLEGE)

    assert is_window_open(COLLEGE, BASE) is False
    assert is_window_open(OTHER_COLLEGE, BASE) is True


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (-timedelta(microseconds=1), False),
        (timedelta(0), True),
        (timedelta(hours=1), True),
        (timedelta(hours=2), False),
        (timedelta(hours=2, microseconds=1), False),
    ],
)
def test_window_boundaries(offset, expected):
    make_window(start_at=BASE, end_at=BASE + timedelta(hours=2))

    assert is_window_open(COLLEGE, BASE + offset) is expected


def test_get_open_window_returns_window_instance():
    window = make_window(start_at=BASE - timedelta(hours=1), end_at=BASE + timedelta(hours=1))

    found = get_open_window(COLLEGE, BASE)

    assert found is not None
    assert found.pk == window.pk


def test_naive_datetime_is_interpreted_in_project_timezone():
    start = timezone.make_aware(datetime(2026, 6, 1, 10, 0, 0))
    end = timezone.make_aware(datetime(2026, 6, 1, 14, 0, 0))
    make_window(start_at=start, end_at=end)

    assert is_window_open(COLLEGE, datetime(2026, 6, 1, 12, 0, 0)) is True
    assert is_window_open(COLLEGE, datetime(2026, 6, 1, 15, 0, 0)) is False


def test_empty_college_is_closed():
    make_window(start_at=BASE - timedelta(hours=1), end_at=BASE + timedelta(hours=1))

    assert is_window_open("", BASE) is False
    assert is_window_open(None, BASE) is False


def test_require_window_open_returns_window():
    window = make_window(start_at=BASE - timedelta(hours=1), end_at=BASE + timedelta(hours=1))

    assert require_window_open(COLLEGE, BASE).pk == window.pk


def test_require_window_open_without_window_raises_409():
    with pytest.raises(WindowClosed) as excinfo:
        require_window_open(COLLEGE, BASE)

    assert excinfo.value.status_code == 409
    assert excinfo.value.default_code == "WINDOW_CLOSED"
    assert "当前不在组寝开放时间内" in str(excinfo.value)


def test_require_window_open_after_end_raises_409():
    make_window(start_at=BASE - timedelta(hours=2), end_at=BASE)

    with pytest.raises(WindowClosed):
        require_window_open(COLLEGE, BASE)


def test_window_closed_uses_contract_error_envelope():
    from apps.accounts.exceptions import accounts_exception_handler

    response = accounts_exception_handler(WindowClosed(), {})

    assert response is not None
    assert response.status_code == 409
    assert response.data == {
        "code": "WINDOW_CLOSED",
        "message": "当前不在组寝开放时间内",
        "detail": None,
    }
