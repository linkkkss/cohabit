"""六维计算（docs/03 §2.2、§8.3）。"""

from __future__ import annotations

import pytest

from apps.profiles.constants import DIMENSIONS
from apps.profiles.dims import (
    compute_dims,
    dims_are_valid,
    hard_score,
    round_half_up,
    round_half_up_int,
    soft_score,
)
from apps.profiles.tests.helpers import full_hard, full_soft


def test_round_half_up():
    assert round_half_up(2.4) == 2
    assert round_half_up(2.5) == 3
    assert round_half_up(74.5) == 75
    assert round_half_up(74.45, 1) == 74.5
    assert round_half_up_int(48.5) == 49


def test_soft_score():
    assert soft_score(1) == 0
    assert soft_score(3) == 50
    assert soft_score(5) == 100
    for bad in (True, False, 0, 6, "3", 3.0, None):
        assert soft_score(bad) is None


def test_hard_score():
    assert hard_score("smoke", {"smoke": "no"}) == 100
    assert hard_score("smoke", {"smoke": "sometimes"}) == 50
    assert hard_score("smoke", {"smoke": "yes"}) == 0
    assert hard_score("alcohol", {"alcohol": "never"}) is None
    assert hard_score("alcohol", {"alcohol": "social"}) is None
    assert hard_score("smoke", {}) is None


def test_compute_dims_all_high():
    hard = full_hard(
        sleep_time="before23",
        wake_time="before7",
        late_return="never",
        snore="no",
        game_noise="never",
        clean_freq="daily",
        smoke="no",
        pet="has_pet",
        visitor_freq="never",
        ac_temp="medium",
        alcohol="never",
    )
    dims = compute_dims(hard, full_soft(5))
    assert dims == {
        "sleep": 100,
        "clean": 100,
        "social": 100,
        "noise": 100,
        "boundary": 100,
        "spend": 100,
    }


def test_compute_dims_boundary_rounds_half_up():
    # boundary = 0.7*50 + 0.3*avg(smoke 50, pet 50, visitor 35) = 48.5 -> 49
    hard = full_hard(smoke="sometimes", pet="ok", visitor_freq="sometimes")
    dims = compute_dims(hard, full_soft(3))
    assert dims["boundary"] == 49


def test_compute_dims_boundary_docs_example_is_75():
    # docs/03 §2.2 修正后示例：soft=4(75) + smoke=no(100)/pet=ok(50)/
    # visitor_freq=rarely(70) -> 74.5 -> half-up 75（旧示例 74 已废弃）。
    hard = full_hard(smoke="no", pet="ok", visitor_freq="rarely")
    dims = compute_dims(hard, full_soft(4))
    assert dims["boundary"] == 75


def test_compute_dims_missing_hard_uses_soft_only():
    dims = compute_dims({}, full_soft(4))
    # sleep_regular=4 -> 75；其余软指标=75
    for dimension in DIMENSIONS:
        assert dims[dimension] == 75


def test_compute_dims_all_low():
    hard = full_hard(
        sleep_time="after01",
        wake_time="after9",
        late_return="often",
        snore="yes",
        game_noise="often",
        clean_freq="rarely",
        smoke="yes",
        pet="no_pet",
        visitor_freq="often",
        ac_temp="cool",
        alcohol="often",
    )
    dims = compute_dims(hard, full_soft(1))
    assert dims == {dimension: 0 for dimension in DIMENSIONS}


def test_dims_are_valid():
    dims = {dimension: 50 for dimension in DIMENSIONS}
    assert dims_are_valid(dims)
    assert not dims_are_valid({})
    assert not dims_are_valid({**dims, "sleep": 101})
    assert not dims_are_valid({**dims, "unknown": 50})
    assert not dims_are_valid({key: value for key, value in dims.items() if key != "social"})


def test_compute_dims_rejects_bad_soft_type():
    dims = compute_dims({}, {**full_soft(3), "clean": True})
    assert dims["clean"] == 0


@pytest.mark.parametrize("value", [0, 6, "3", 3.0, True])
def test_compute_dims_soft_invalid(value):
    dims = compute_dims({}, {**full_soft(3), "clean": value})
    assert dims["clean"] == 0
