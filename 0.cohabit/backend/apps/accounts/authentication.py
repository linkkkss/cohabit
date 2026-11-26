"""JWT 认证：认证成功时顺带刷新 ``User.last_active_at``（docs/04 §3.1）。

写库只有一条 ``UPDATE``，且按 ``TOUCH_INTERVAL`` 节流：同一用户 5 分钟内最多
写一次，避免每个请求都产生写放大。活跃时间只是展示信息，写失败不影响鉴权。
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import User

TOUCH_INTERVAL = timedelta(minutes=5)


class LastActiveJWTAuthentication(JWTAuthentication):
    """标准 JWT 认证 + 最近活跃时间。"""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, _token = result
        self._touch(user)
        return result

    @staticmethod
    def _touch(user: User) -> None:
        now = timezone.now()
        cutoff = now - TOUCH_INTERVAL
        if user.last_active_at is not None and user.last_active_at > cutoff:
            return
        # 条件更新：并发请求同时判定“陈旧”时也只有一条真正落库。
        User.objects.filter(pk=user.pk).filter(
            Q(last_active_at__isnull=True) | Q(last_active_at__lte=cutoff)
        ).update(last_active_at=now)
        user.last_active_at = now
