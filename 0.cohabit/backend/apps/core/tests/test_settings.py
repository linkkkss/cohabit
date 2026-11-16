"""开发环境设置测试（docs/08 缺陷清单 P3-1）。

Vite 代理（5173/5174/4173）会把浏览器 Origin 原样转给 Django，而 Host 变成后端
地址；``config.settings.dev`` 必须默认信任这些本地 Origin，Django Admin 才能在
代理下完成 CSRF 校验并登录。
"""

from __future__ import annotations

import importlib

import pytest

VITE_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
}


def load_dev_settings():
    """按当前环境变量重新加载 dev.py，返回它计算出的设置。"""
    return importlib.reload(importlib.import_module("config.settings.dev"))


@pytest.fixture
def clean_csrf_env(monkeypatch):
    """测试前后清除 CSRF 覆盖变量，避免污染同进程的其他用例。"""
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)
    yield
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)
    load_dev_settings()


def test_dev_settings_trust_local_vite_origins(clean_csrf_env):
    dev = load_dev_settings()

    assert set(dev.CSRF_TRUSTED_ORIGINS) >= VITE_ORIGINS


def test_dev_settings_csrf_origins_can_be_overridden_by_env(monkeypatch):
    monkeypatch.setenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://admin.example.com, http://127.0.0.1:9000",
    )

    dev = load_dev_settings()

    assert dev.CSRF_TRUSTED_ORIGINS == [
        "https://admin.example.com",
        "http://127.0.0.1:9000",
    ]

    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)
    load_dev_settings()
