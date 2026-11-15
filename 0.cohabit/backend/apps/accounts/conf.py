"""认证运行期配置：settings 已由基础层固定，这里只读并用 env 做开发开关覆盖。"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from django.conf import settings

# 开发期固定验证码（开发手册 Q10：上线再限校域名/真实邮件）。
DEV_VERIFICATION_CODE = "123456"
VERIFICATION_CODE_TTL = 10 * 60
VERIFICATION_CODE_SEEN_TTL = 30 * 60

# docs/04 §1.2 refresh Cookie 约定。
COOKIE_NAME = "refresh"
COOKIE_PATH = "/api/auth/"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60
COOKIE_SAMESITE = "Lax"

# 开发态前端/后端来源；settings 未配置 ALLOWED_ORIGINS 时用于刷新/注销的来源校验。
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://testserver",
)

_TRUTHY = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def invite_required() -> bool:
    """注册是否必须邀请码（docs/03 §1.3.4：开发默认关闭）。"""
    return _env_flag("INVITE_REQUIRED", bool(getattr(settings, "INVITE_REQUIRED", False)))


def cookie_secure() -> bool:
    """生产环境 refresh Cookie 必须带 Secure（docs/04 §1.2）。"""
    return not bool(getattr(settings, "DEBUG", False))


def access_expires_in() -> int:
    """access 有效期（秒），与 SIMPLE_JWT.ACCESS_TOKEN_LIFETIME 保持一致。"""
    return int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())


def allowed_origins() -> frozenset[str]:
    """刷新/注销允许的来源：env ALLOWED_ORIGINS → CSRF_TRUSTED_ORIGINS → 开发默认值。"""
    origins = {
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }
    origins.update(getattr(settings, "CSRF_TRUSTED_ORIGINS", None) or [])
    origins.update(DEFAULT_ALLOWED_ORIGINS)
    return frozenset(origin.rstrip("/") for origin in origins)


def _referer_origin(referer: str | None) -> str | None:
    if not referer:
        return None
    parts = urlsplit(referer)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def request_origin_allowed(meta: dict[str, str]) -> bool:
    """校验来源：Origin 优先，缺失时回退 Referer；两者都缺省视为同源/非浏览器请求。"""
    origin = meta.get("HTTP_ORIGIN") or _referer_origin(meta.get("HTTP_REFERER"))
    if not origin:
        return True
    return origin.rstrip("/") in allowed_origins()
