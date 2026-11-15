"""并发路径（docs/02 §11.7）：双击 confirm、反向同时发起。"""

from __future__ import annotations

import threading

import pytest
from django.db import connections
from rest_framework.test import APIClient

from apps.connections.models import ConnectionRequest
from apps.rooms.models import Room

from .helpers import (
    auth_client,
    error_code,
    make_connection,
    open_window,
    pair,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _close_connections():
    yield
    connections.close_all()


def _run(workers: list) -> None:
    threads = [threading.Thread(target=worker) for worker in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)


def test_double_click_confirm_transitions_once():
    initiator, target = pair()
    open_window()
    row = make_connection(initiator=initiator, target=target)
    accept = auth_client(target).post(f"/api/connections/{row.pk}/accept")
    assert accept.status_code == 200

    barrier = threading.Barrier(2)
    codes: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        connections.close_all()
        client = APIClient()
        client.force_authenticate(initiator)
        barrier.wait()
        try:
            response = client.post(f"/api/connections/{row.pk}/confirm")
            with lock:
                codes.append(response.status_code)
        finally:
            connections.close_all()

    _run([worker, worker])

    assert sorted(codes) == [200, 409]
    row.refresh_from_db()
    assert row.status == "CONFIRMING"
    assert row.initiator_confirm_at is not None
    assert Room.objects.count() == 0


def test_reverse_creation_race_allows_single_open_request():
    first, second = pair()
    open_window()

    barrier = threading.Barrier(2)
    results: list[tuple[int, str]] = []
    lock = threading.Lock()

    def worker(user, other) -> None:
        connections.close_all()
        client = APIClient()
        client.force_authenticate(user)
        barrier.wait()
        try:
            response = client.post(
                "/api/connections",
                {"type": "INVITE", "target_uid": other.uid, "capacity_pref": 4},
                format="json",
            )
            with lock:
                results.append((response.status_code, error_code(response)))
        finally:
            connections.close_all()

    _run([lambda: worker(first, second), lambda: worker(second, first)])

    assert sorted(status for status, _ in results) == [201, 409]
    assert [code for _, code in results if code == "DUPLICATE_REQUEST"] == [
        "DUPLICATE_REQUEST"
    ]
    assert ConnectionRequest.objects.filter(status="PENDING").count() == 1
