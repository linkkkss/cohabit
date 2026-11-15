"""认证业务逻辑：验证码、注册、登录、刷新、注销与 refresh Cookie（docs/04 §2）。"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import ExpiredTokenError, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import conf, throttling
from apps.accounts.exceptions import ApiError
from apps.accounts.models import InviteCode, User

logger = logging.getLogger(__name__)


def _code_key(email: str) -> str:
    return f"auth:code:{email}"


def _code_seen_key(email: str) -> str:
    return f"auth:code-seen:{email}"


def _issue_code(email: str) -> str:
    code = conf.DEV_VERIFICATION_CODE if settings.DEBUG else f"{secrets.randbelow(10**6):06d}"
    cache.set(_code_key(email), code, timeout=conf.VERIFICATION_CODE_TTL)
    cache.set(_code_seen_key(email), True, timeout=conf.VERIFICATION_CODE_SEEN_TTL)
    return code


def send_verification_code(email: str) -> str | None:
    """发送验证码；DEBUG 下直接返回固定码（docs/04 §2.1 的 dev_code）。"""
    throttling.enforce_send_code(email)
    code = _issue_code(email)
    if settings.DEBUG:
        return code
    try:
        send_mail(
            "Cohabit 邮箱验证码",
            f"你的验证码是 {code}，{conf.VERIFICATION_CODE_TTL // 60} 分钟内有效。",
            None,
            [email],
        )
    except Exception:  # pragma: no cover - 邮件通道未配置时不影响接口语义
        logger.warning("验证码邮件发送失败", exc_info=True)
    return None


def _verify_code(email: str, code: str) -> None:
    stored = cache.get(_code_key(email))
    # 开发期固定验证码始终可用（开发手册 Q10）。
    if settings.DEBUG and code == conf.DEV_VERIFICATION_CODE:
        cache.delete(_code_key(email))
        return
    if stored is None:
        if cache.get(_code_seen_key(email)):
            raise ApiError("CODE_EXPIRED", status_code=400)
        raise ApiError("CODE_INVALID", status_code=400)
    if code != stored:
        raise ApiError("CODE_INVALID", status_code=400)
    cache.delete(_code_key(email))


def _consume_invite(raw_code: Any) -> None:
    """加锁占用一次邀请码；须在事务内调用（docs/03 §1.3.4）。

    失败原因（不存在/停用/过期/次数用尽）对外统一为 400 INVITE_INVALID。
    """
    value = str(raw_code or "").strip().upper()
    if not value:
        if conf.invite_required():
            raise ApiError("INVITE_REQUIRED", status_code=403)
        return
    try:
        invite = InviteCode.objects.select_for_update().get(code=value)
    except InviteCode.DoesNotExist:
        raise ApiError("INVITE_INVALID", status_code=400) from None
    if not invite.is_usable():
        raise ApiError("INVITE_INVALID", status_code=400)
    invite.used_count += 1
    invite.save(update_fields=["used_count", "updated_at"])


def register_user(data: dict[str, Any], *, client_ip: str) -> User:
    """注册：限频 → 验证码 → 邮箱唯一 → 占用邀请码并建号（同一事务）。"""
    throttling.enforce_register(client_ip)
    email = str(data["email"]).strip().lower()
    _verify_code(email, str(data["code"]))
    invite_code = data.get("invite_code")
    if not str(invite_code or "").strip() and conf.invite_required():
        raise ApiError("INVITE_REQUIRED", status_code=403)
    if User.objects.filter(email=email).exists():
        raise ApiError("EMAIL_TAKEN", status_code=409)
    try:
        with transaction.atomic():
            _consume_invite(invite_code)
            return User.objects.create_user(
                email=email,
                password=data["password"],
                nickname=data["nickname"],
                gender=data["gender"],
                grade=data["grade"],
                college=data["college"],
                major=data.get("major", ""),
            )
    except IntegrityError as exc:  # 并发注册同一邮箱
        raise ApiError("EMAIL_TAKEN", status_code=409) from exc


def login_user(email: str, password: str, *, client_ip: str) -> User:
    """邮箱密码登录；失败统一 401，禁用账号 403（docs/04 §2.3）。"""
    normalized = (email or "").strip().lower()
    throttling.enforce_login_allowed(normalized, client_ip)
    user = User.objects.filter(email=normalized).first()
    if user is None or not user.check_password(password):
        throttling.record_login_failure(normalized, client_ip)
        raise ApiError("INVALID_CREDENTIALS", status_code=401)
    if user.status == User.Status.DISABLED or not user.is_active:
        raise ApiError("ACCOUNT_DISABLED", status_code=403)
    throttling.clear_login_failures(normalized, client_ip)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login", "updated_at"])
    return user


def issue_tokens(user: User) -> tuple[str, RefreshToken]:
    """签发 access（30 分钟）+ refresh（7 天，带黑名单登记）。"""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), refresh


def _decode_refresh(raw_refresh: str) -> RefreshToken:
    try:
        return RefreshToken(raw_refresh)
    except ExpiredTokenError as exc:
        raise ApiError("TOKEN_EXPIRED", status_code=401) from exc
    except TokenError as exc:
        raise ApiError("TOKEN_INVALID", status_code=401) from exc


def _refresh_throttle_key(raw_refresh: str, token: RefreshToken) -> str:
    jti = token.get(jwt_settings.JTI_CLAIM)
    if jti:
        return str(jti)
    return hashlib.sha256(raw_refresh.encode("utf-8")).hexdigest()[:32]


def refresh_session(raw_refresh: str | None) -> tuple[str, RefreshToken]:
    """轮换 refresh：旧 token 入黑名单，返回新 access + 新 refresh（docs/04 §2.4）。"""
    if not raw_refresh:
        raise ApiError("TOKEN_INVALID", status_code=401)
    token = _decode_refresh(raw_refresh)
    throttling.enforce_refresh(_refresh_throttle_key(raw_refresh, token))
    user_id = token.get(jwt_settings.USER_ID_CLAIM)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    if user is None:
        raise ApiError("TOKEN_INVALID", status_code=401)
    if user.status == User.Status.DISABLED or not user.is_active:
        raise ApiError("ACCOUNT_DISABLED", status_code=403)
    token.blacklist()
    new_refresh = RefreshToken.for_user(user)
    return str(new_refresh.access_token), new_refresh


def logout_session(raw_refresh: str | None) -> None:
    """注销：把 refresh 加入黑名单；无效/已黑名单 token 一律静默（docs/04 §2.5）。"""
    if not raw_refresh:
        return
    try:
        token = RefreshToken(raw_refresh)
    except TokenError:
        return
    try:
        token.blacklist()
    except Exception:  # pragma: no cover - 黑名单表异常不应阻断注销
        logger.warning("注销时 refresh 入黑名单失败", exc_info=True)


def attach_refresh_cookie(response: Response, refresh: RefreshToken) -> None:
    response.set_cookie(
        conf.COOKIE_NAME,
        str(refresh),
        max_age=conf.COOKIE_MAX_AGE,
        path=conf.COOKIE_PATH,
        httponly=True,
        secure=conf.cookie_secure(),
        samesite=conf.COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        conf.COOKIE_NAME,
        path=conf.COOKIE_PATH,
        samesite=conf.COOKIE_SAMESITE,
    )
