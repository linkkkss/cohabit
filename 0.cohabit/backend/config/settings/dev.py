"""Local development settings."""
from .base import *  # noqa: F401,F403
from .base import env_list

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# Vite dev/preview 代理 /admin 到后端时，浏览器 Origin 是前端地址而 Django 看到的
# Host 是代理目标地址，需要显式信任本地 Vite 端口（5173/5174/4173）。
# 仍可用环境变量 ``CSRF_TRUSTED_ORIGINS``（逗号分隔）整体覆盖。
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    ",".join(
        (
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "http://127.0.0.1:4173",
            "http://localhost:4173",
        )
    ),
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
