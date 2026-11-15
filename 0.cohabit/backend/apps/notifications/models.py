"""notifications 领域模型：站内信（docs/03 §1.7、§9）。"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """站内信：只增不改，除 ``read_at`` 外不更新（docs/03 §1.7）。"""

    class Type(models.TextChoices):
        CONNECTION_RECEIVED = "CONNECTION_RECEIVED", "收到组寝请求"
        CONTACT_SHARED = "CONTACT_SHARED", "联系方式互见"
        CONFIRM_PENDING = "CONFIRM_PENDING", "对方已确认"
        CONFIRMED = "CONFIRMED", "组寝成功"
        DECLINED = "DECLINED", "请求被拒绝"
        SYSTEM = "SYSTEM", "系统通知"
        MEMBER_JOINED = "MEMBER_JOINED", "成员加入"
        ROOM_FULL = "ROOM_FULL", "寝室满员"
        MEMBER_LEFT = "MEMBER_LEFT", "成员退出"
        ROOM_LOCKED = "ROOM_LOCKED", "寝室锁定"
        ROOM_DISSOLVED = "ROOM_DISSOLVED", "寝室解散"
        ROOM_ARCHIVED = "ROOM_ARCHIVED", "寝室归档"
        TRANSFER_RECEIVED = "TRANSFER_RECEIVED", "收到房主转让"
        TRANSFER_ACCEPTED = "TRANSFER_ACCEPTED", "转让已接受"
        TRANSFER_DECLINED = "TRANSFER_DECLINED", "转让被拒绝"
        TRANSFER_EXPIRED = "TRANSFER_EXPIRED", "转让已过期"
        TRANSFER_CANCELLED = "TRANSFER_CANCELLED", "转让已取消"
        WINDOW_CLOSING = "WINDOW_CLOSING", "组寝窗口即将关闭"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="接收者",
    )
    type = models.CharField("类型", max_length=24, choices=Type.choices)
    title = models.CharField("标题", max_length=60)
    payload = models.JSONField("载荷", default=dict, blank=True)
    read_at = models.DateTimeField("已读时间", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notifications_notification"
        verbose_name = "通知"
        verbose_name_plural = "通知"
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="idx_notif_user_created",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.type}:{self.title}"
