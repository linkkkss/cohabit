"""connections 领域模型：邀请/申请状态机（docs/03 §1.6）。"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel
from apps.rooms.models import Room

# OPEN = 在途状态；终态不再占用部分唯一索引（docs/03 §1.6）。
OPEN_STATUSES = ("PENDING", "CONTACT_SHARED", "CONFIRMING")


class ConnectionRequest(BaseModel):
    """组寝请求：INVITE / APPLY，OPEN 三态唯一约束由数据库兜底。"""

    class Type(models.TextChoices):
        INVITE = "INVITE", "邀请组寝"
        APPLY = "APPLY", "申请入寝"

    class Status(models.TextChoices):
        PENDING = "PENDING", "待对方确认"
        CONTACT_SHARED = "CONTACT_SHARED", "联系方式互见"
        CONFIRMING = "CONFIRMING", "待二次确认"
        CONFIRMED = "CONFIRMED", "组寝成立"
        DECLINED = "DECLINED", "已拒绝"
        CANCELLED = "CANCELLED", "已取消"
        EXPIRED = "EXPIRED", "已过期"

    class CloseReason(models.TextChoices):
        DECLINED = "DECLINED", "对方拒绝"
        INITIATOR_CANCEL = "INITIATOR_CANCEL", "发起人撤回"
        END_UNDERSTANDING = "END_UNDERSTANDING", "结束了解"
        TIMEOUT = "TIMEOUT", "超时"
        FULL = "FULL", "房间已满"
        LOCKED = "LOCKED", "房间已锁定"
        ROOM_DISSOLVED = "ROOM_DISSOLVED", "房间已解散"
        ARCHIVED = "ARCHIVED", "窗口结束归档"
        USER_DISABLED = "USER_DISABLED", "用户被禁用"
        RATE_LIMITED = "RATE_LIMITED", "触发限频"
        ADMIN = "ADMIN", "管理员关闭"
        BLOCKED = "BLOCKED", "拉黑"
        AUTO_CANCELLED = "AUTO_CANCELLED", "自动取消"

    type = models.CharField("类型", max_length=10, choices=Type.choices)
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connection_requests_sent",
        verbose_name="发起人",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connection_requests_received",
        verbose_name="目标",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        related_name="connection_requests",
        verbose_name="寝室",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    message = models.CharField("留言", max_length=200, blank=True, default="")
    capacity_pref = models.PositiveSmallIntegerField(
        "期望容量",
        choices=Room.Capacity.choices,
        null=True,
        blank=True,
        help_text="仅人-人 INVITE 使用；其余必须为空",
    )
    contact_shared_at = models.DateTimeField("联系方式互见时间", null=True, blank=True)
    initiator_confirm_at = models.DateTimeField(
        "发起人确认时间", null=True, blank=True
    )
    target_confirm_at = models.DateTimeField("目标确认时间", null=True, blank=True)
    expires_at = models.DateTimeField(
        "过期时间",
        db_index=True,
        null=True,
        blank=True,
        help_text="CONFIRMED 为空；其余在途状态必有值",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="connection_requests_closed",
        verbose_name="关闭操作者",
        null=True,
        blank=True,
        help_text="cron 关闭时为空",
    )
    close_reason = models.CharField(
        "关闭原因",
        max_length=20,
        choices=CloseReason.choices,
        blank=True,
        default="",
        help_text="CONFIRMED 为空；其余终态必有值",
    )
    version = models.PositiveIntegerField("版本", default=0)

    class Meta:
        db_table = "connections_connection_request"
        verbose_name = "组寝请求"
        verbose_name_plural = "组寝请求"
        indexes = [
            models.Index(
                fields=["target", "status"],
                name="idx_conn_target_status",
            ),
            models.Index(
                fields=["initiator", "status"],
                name="idx_conn_initiator_status",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="idx_conn_status_expires",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(initiator=F("target")),
                name="ck_conn_not_self",
            ),
            models.CheckConstraint(
                condition=~Q(type="APPLY") | Q(room__isnull=False),
                name="ck_conn_apply_room",
            ),
            models.CheckConstraint(
                condition=Q(capacity_pref__isnull=True)
                | Q(capacity_pref__in=[2, 4, 6]),
                name="ck_conn_capacity_pref",
            ),
            models.CheckConstraint(
                condition=(
                    Q(type="INVITE", room__isnull=True, capacity_pref__isnull=False)
                    | (
                        ~Q(type="INVITE", room__isnull=True)
                        & Q(capacity_pref__isnull=True)
                    )
                ),
                name="ck_conn_capacity_scope",
            ),
            models.UniqueConstraint(
                fields=["initiator", "target"],
                condition=Q(status__in=OPEN_STATUSES),
                name="uq_open_pair",
            ),
            models.UniqueConstraint(
                fields=["room", "initiator"],
                condition=Q(type="APPLY", status__in=OPEN_STATUSES),
                name="uq_open_apply_room",
            ),
            models.UniqueConstraint(
                fields=["room", "target"],
                condition=Q(
                    type="INVITE",
                    room__isnull=False,
                    status__in=OPEN_STATUSES,
                ),
                name="uq_open_invite_room_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type}:{self.initiator_id}->{self.target_id}({self.status})"
