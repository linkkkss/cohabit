"""accounts 测试公共 fixture。"""

from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _debug_mode(settings):
    """pytest-django 默认把 DEBUG 置 False；这里恢复开发态语义（固定验证码/dev_code）。"""
    settings.DEBUG = True
    return settings


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()
