"""通知序列化（docs/04 §4.5、openapi ``Notification``）。"""

from __future__ import annotations

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """通知列表/已读响应；payload 由服务层保证非敏感。"""

    class Meta:
        model = Notification
        fields = ("id", "type", "title", "payload", "read_at", "created_at")
        read_only_fields = fields
