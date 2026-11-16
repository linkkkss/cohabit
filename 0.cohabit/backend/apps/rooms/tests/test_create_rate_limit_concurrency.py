"""建寝每日限频的并发安全（docs/02 §11.2 / docs/04 §1.9）。"""

from __future__ import annotations

import threading

import pytest
from django.db import connections, transaction

from apps.rooms import services
from apps.rooms.exceptions import RoomRateLimited
from apps.rooms.models import Room, RoomMember

from .helpers import make_user, open_window

pytestmark = pytest.mark.django_db(transaction=True)


def test_concurrent_confirms_cannot_exceed_daily_limit():
    open_window()
    owner = make_user(uid="1300000101", email="race-owner@example.com")
    targets = [
        make_user(uid=f"130000020{index}", email=f"race-target-{index}@example.com")
        for index in range(6)
    ]

    barrier = threading.Barrier(len(targets))
    lock = threading.Lock()
    succeeded: list[int] = []
    limited: list[int] = []
    errors: list[str] = []

    def worker(index: int) -> None:
        connections.close_all()
        barrier.wait()
        try:
            with transaction.atomic():
                room = services.create_room_for_pair(owner, targets[index], 4)
                # 释放 owner 的 ACTIVE 成员行，使下一轮仍可进入限频判断；
                # 事务提交后 Room 行仍参与当日计数。
                RoomMember.objects.filter(room=room).update(
                    status=RoomMember.Status.LEFT
                )
            with lock:
                succeeded.append(index)
        except RoomRateLimited:
            with lock:
                limited.append(index)
        except Exception as exc:  # noqa: BLE001 - 测试需要暴露并发异常
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    assert len(succeeded) == services.DAILY_ROOM_LIMIT
    assert len(limited) == 1
    assert Room.objects.filter(owner=owner).count() == services.DAILY_ROOM_LIMIT
