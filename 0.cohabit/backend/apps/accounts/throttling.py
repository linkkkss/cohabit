"""轻量限频：基于 Django cache（开发 LocMemCache），执行 docs/04 §1.9 的限制。"""

from __future__ import annotations

import math
import time

from django.core.cache import cache

from apps.accounts.exceptions import ApiError

SEND_CODE_INTERVAL_SECONDS = 60
SEND_CODE_DAILY_LIMIT = 10
SEND_CODE_DAILY_WINDOW = 24 * 60 * 60
REGISTER_HOURLY_LIMIT = 5
REGISTER_HOURLY_WINDOW = 60 * 60
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW = 15 * 60
REFRESH_MINUTE_LIMIT = 30
REFRESH_MINUTE_WINDOW = 60


def _retry_after(deadline: float) -> int:
    return max(1, math.ceil(deadline - time.time()))


def _read_window(key: str) -> tuple[int, float] | None:
    entry = cache.get(key)
    if isinstance(entry, tuple) and len(entry) == 2:
        return int(entry[0]), float(entry[1])
    return None


def _write_window(key: str, count: int, reset_at: float) -> None:
    cache.set(key, (count, reset_at), timeout=max(1, math.ceil(reset_at - time.time())))


def _bump_window(key: str, window_seconds: int, limit: int, code: str, message: str) -> None:
    """固定窗口计数：达到上限即抛 429，并带 Retry-After。"""
    now = time.time()
    window = _read_window(key)
    if window is None or window[1] <= now:
        window = (0, now + window_seconds)
    if window[0] >= limit:
        raise ApiError(code, message, 429, retry_after=_retry_after(window[1]))
    _write_window(key, window[0] + 1, window[1])


def enforce_send_code(email: str) -> None:
    """同邮箱 60 秒 1 次、每日 10 次（docs/04 §1.9）。"""
    now = time.time()
    interval_key = f"auth:throttle:send-code:interval:{email}"
    deadline = cache.get(interval_key)
    if isinstance(deadline, float) and deadline > now:
        raise ApiError(
            "RATE_LIMITED",
            "验证码发送过于频繁，请稍后再试",
            429,
            retry_after=_retry_after(deadline),
        )
    daily_key = f"auth:throttle:send-code:daily:{email}"
    daily = _read_window(daily_key)
    if daily is None or daily[1] <= now:
        daily = (0, now + SEND_CODE_DAILY_WINDOW)
    if daily[0] >= SEND_CODE_DAILY_LIMIT:
        raise ApiError(
            "RATE_LIMITED",
            "今日验证码发送次数已达上限",
            429,
            retry_after=_retry_after(daily[1]),
        )
    _write_window(daily_key, daily[0] + 1, daily[1])
    cache.set(interval_key, now + SEND_CODE_INTERVAL_SECONDS, timeout=SEND_CODE_INTERVAL_SECONDS)


def enforce_register(client_ip: str) -> None:
    """同 IP 每小时 5 次注册尝试（docs/04 §1.9）。"""
    _bump_window(
        f"auth:throttle:register:{client_ip}",
        REGISTER_HOURLY_WINDOW,
        REGISTER_HOURLY_LIMIT,
        "RATE_LIMITED",
        "注册过于频繁，请稍后再试",
    )


def _login_key(email: str, client_ip: str) -> str:
    return f"auth:throttle:login:{email}:{client_ip}"


def enforce_login_allowed(email: str, client_ip: str) -> None:
    """同邮箱+IP 15 分钟内 5 次失败后拒绝（docs/04 §1.9）。"""
    now = time.time()
    window = _read_window(_login_key(email, client_ip))
    if window and window[1] > now and window[0] >= LOGIN_FAILURE_LIMIT:
        raise ApiError(
            "RATE_LIMITED",
            "登录尝试过于频繁，请稍后再试",
            429,
            retry_after=_retry_after(window[1]),
        )


def record_login_failure(email: str, client_ip: str) -> None:
    _bump_window(
        _login_key(email, client_ip),
        LOGIN_FAILURE_WINDOW,
        # 计数到上限后不再递增，避免持续失败把窗口不断刷新；上限判断在 enforce。
        LOGIN_FAILURE_LIMIT,
        "RATE_LIMITED",
        "登录尝试过于频繁，请稍后再试",
    )


def clear_login_failures(email: str, client_ip: str) -> None:
    cache.delete(_login_key(email, client_ip))


def enforce_refresh(jti: str) -> None:
    """同一 refresh 每分钟最多 30 次（docs/04 §1.9，超限为 THROTTLED）。"""
    _bump_window(
        f"auth:throttle:refresh:{jti}",
        REFRESH_MINUTE_WINDOW,
        REFRESH_MINUTE_LIMIT,
        "THROTTLED",
        "刷新过于频繁，请稍后再试",
    )
