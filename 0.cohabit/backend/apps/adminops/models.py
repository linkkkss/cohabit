"""adminops 领域模型：时间窗、举报、拉黑、审计（docs/03 §1.8）。"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel


class TimeWindow(BaseModel):
    """按学院的开窗配置；无记录=关闭（docs/03 §1.8.1）。"""

    college = models.CharField(
        "学院",
        max_length=50,
        help_text="一个学院一条；无记录表示未开窗",
    )
    start_at = models.DateTimeField("开始时间")
    end_at = models.DateTimeField("结束时间")
    note = models.CharField("备注", max_length=100, blank=True, default="")

    class Meta:
        db_table = "adminops_time_window"
        verbose_name = "组寝时间窗"
        verbose_name_plural = "组寝时间窗"
        constraints = [
            models.UniqueConstraint(
                fields=["college"],
                name="uq_window_college",
            ),
            models.CheckConstraint(
                condition=Q(start_at__lt=F("end_at")),
                name="ck_window_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.college}: {self.start_at} ~ {self.end_at}"


class Report(BaseModel):
    """举报：只进 Admin 人工处理，目标不建外键（docs/03 §1.8.2）。"""

    class TargetType(models.TextChoices):
        USER = "USER", "用户"
        ROOM = "ROOM", "寝室"
        CONNECTION = "CONNECTION", "组寝请求"

    class Status(models.TextChoices):
        OPEN = "OPEN", "待处理"
        RESOLVED = "RESOLVED", "已处理"
        DISMISSED = "DISMISSED", "已驳回"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
        verbose_name="举报人",
    )
    target_type = models.CharField(
        "目标类型",
        max_length=12,
        choices=TargetType.choices,
    )
    target_id = models.PositiveBigIntegerField("目标 id")
    reason = models.CharField("举报原因", max_length=200)
    status = models.CharField(
        "状态",
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reports_handled",
        verbose_name="处理人",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "adminops_report"
        verbose_name = "举报"
        verbose_name_plural = "举报"
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="idx_report_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.target_type}:{self.target_id}({self.status})"


class Block(BaseModel):
    """拉黑：双向不可见；重复拉黑由唯一约束兜底（docs/03 §1.3.3）。"""

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_created",
        verbose_name="拉黑者",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_received",
        verbose_name="被拉黑者",
    )

    class Meta:
        db_table = "adminops_block"
        verbose_name = "拉黑"
        verbose_name_plural = "拉黑"
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="uq_block_pair",
            ),
            models.CheckConstraint(
                condition=~Q(blocker=F("blocked")),
                name="ck_block_not_self",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.blocker_id}->{self.blocked_id}"


class AuditLog(models.Model):
    """审计日志：只增不改、永久保留，无 ``updated_at``（docs/03 §1.8.3）。"""

    class TargetType(models.TextChoices):
        USER = "USER", "用户"
        ROOM = "ROOM", "寝室"
        CONNECTION = "CONNECTION", "组寝请求"
        TRANSFER = "TRANSFER", "房主转让"
        NOTIFICATION = "NOTIFICATION", "通知"
        WINDOW = "WINDOW", "时间窗"
        REPORT = "REPORT", "举报"
        INVITE = "INVITE", "邀请码"

    id = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        verbose_name="操作者",
        null=True,
        blank=True,
        help_text="cron/系统事件为空",
    )
    action = models.CharField("事件名", max_length=50)
    target_type = models.CharField(
        "目标类型",
        max_length=20,
        choices=TargetType.choices,
    )
    target_id = models.PositiveBigIntegerField("目标 id", null=True, blank=True)
    meta = models.JSONField("元数据", default=dict, blank=True)
    request_id = models.CharField("请求追踪 id", max_length=64, blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "adminops_audit_log"
        verbose_name = "审计日志"
        verbose_name_plural = "审计日志"
        indexes = [
            models.Index(
                fields=["target_type", "target_id"],
                name="idx_audit_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action}@{self.created_at}"
