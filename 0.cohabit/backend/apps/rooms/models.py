"""rooms 领域模型：寝室、成员关系、房主转让（docs/03 §1.5）。"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel

ROOM_CODE_LENGTH = 9
ROOM_CODE_VALIDATOR = RegexValidator(r"^\d{9}$", "寝室号必须是 9 位数字")


class Room(BaseModel):
    """寝室：容量 2/4/6，创建时快照学院/性别（docs/03 §1.5.1）。"""

    class Status(models.TextChoices):
        RECRUITING = "RECRUITING", "招募中"
        FULL = "FULL", "满员"
        LOCKED = "LOCKED", "已锁定"
        ARCHIVED = "ARCHIVED", "已归档"
        DISSOLVED = "DISSOLVED", "已解散"

    class Gender(models.TextChoices):
        MALE = "MALE", "男"
        FEMALE = "FEMALE", "女"

    class Capacity(models.IntegerChoices):
        TWO = 2, "2 人"
        FOUR = 4, "4 人"
        SIX = 6, "6 人"

    code = models.CharField(
        "寝室号",
        max_length=ROOM_CODE_LENGTH,
        unique=True,
        validators=[ROOM_CODE_VALIDATOR],
        help_text="对外寝室号，9 位数字",
    )
    title = models.CharField("标题", max_length=30, blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_rooms",
        verbose_name="房主",
    )
    capacity = models.PositiveSmallIntegerField(
        "容量",
        choices=Capacity.choices,
        default=Capacity.FOUR,
    )
    member_count = models.PositiveSmallIntegerField("成员数", default=1)
    gender = models.CharField(
        "性别快照",
        max_length=10,
        choices=Gender.choices,
        db_index=True,
    )
    college = models.CharField("学院快照", max_length=50, db_index=True)
    major = models.CharField("专业", max_length=50, blank=True, default="")
    tags = models.JSONField("标签", default=list, blank=True)
    status = models.CharField(
        "状态",
        max_length=12,
        choices=Status.choices,
        default=Status.RECRUITING,
    )
    archived_at = models.DateTimeField("归档时间", null=True, blank=True)
    dissolved_at = models.DateTimeField("解散时间", null=True, blank=True)

    class Meta:
        db_table = "rooms_room"
        verbose_name = "寝室"
        verbose_name_plural = "寝室"
        indexes = [
            models.Index(
                fields=["status", "college", "gender"],
                name="idx_room_square",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(capacity__in=[2, 4, 6]),
                name="ck_room_capacity",
            ),
            models.CheckConstraint(
                condition=Q(member_count__lte=F("capacity")),
                name="ck_room_member_count",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.title}".strip()


class RoomMember(BaseModel):
    """寝室成员关系；ACTIVE 才占“一人一 ACTIVE 寝”（docs/03 §1.5.2）。"""

    class Role(models.TextChoices):
        OWNER = "OWNER", "房主"
        MEMBER = "MEMBER", "成员"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "在寝"
        LEFT = "LEFT", "已退出"
        REMOVED = "REMOVED", "已移除"
        ARCHIVED = "ARCHIVED", "已归档"

    class Reason(models.TextChoices):
        VOLUNTARY = "VOLUNTARY", "主动退出"
        REMOVED_BY_OWNER = "REMOVED_BY_OWNER", "房主移除"
        DISSOLVED = "DISSOLVED", "寝室解散"
        ARCHIVED = "ARCHIVED", "窗口归档"
        USER_DISABLED = "USER_DISABLED", "用户禁用"

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="寝室",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_memberships",
        verbose_name="用户",
    )
    role = models.CharField(
        "角色",
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    status = models.CharField(
        "状态",
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    # created_at 即加入时间，不另设 joined_at（docs/03 §1.11）。
    left_at = models.DateTimeField("离开时间", null=True, blank=True)
    reason = models.CharField(
        "原因",
        max_length=50,
        choices=Reason.choices,
        blank=True,
        default="",
    )

    class Meta:
        db_table = "rooms_room_member"
        verbose_name = "寝室成员"
        verbose_name_plural = "寝室成员"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="ACTIVE"),
                name="uq_user_active_room",
            ),
            models.UniqueConstraint(
                fields=["room", "user"],
                condition=Q(status="ACTIVE"),
                name="uq_room_active_user",
            ),
            models.UniqueConstraint(
                fields=["room"],
                condition=Q(role="OWNER", status="ACTIVE"),
                name="uq_room_active_owner",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["ACTIVE", "LEFT", "REMOVED", "ARCHIVED"],
                ),
                name="ck_member_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.room_id}:{self.user_id}({self.role}/{self.status})"


class RoomTransfer(BaseModel):
    """房主转让：同一寝室同时最多一笔 PENDING（docs/03 §1.5.3）。"""

    class Status(models.TextChoices):
        PENDING = "PENDING", "待接受"
        ACCEPTED = "ACCEPTED", "已接受"
        DECLINED = "DECLINED", "已拒绝"
        CANCELLED = "CANCELLED", "已取消"
        EXPIRED = "EXPIRED", "已过期"

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="transfers",
        verbose_name="寝室",
    )
    from_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="room_transfers_sent",
        verbose_name="原房主",
    )
    to_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="room_transfers_received",
        verbose_name="目标成员",
    )
    status = models.CharField(
        "状态",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    expires_at = models.DateTimeField("过期时间")
    decided_at = models.DateTimeField("处理时间", null=True, blank=True)

    class Meta:
        db_table = "rooms_room_transfer"
        verbose_name = "房主转让"
        verbose_name_plural = "房主转让"
        constraints = [
            models.UniqueConstraint(
                fields=["room"],
                condition=Q(status="PENDING"),
                name="uq_room_pending_transfer",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.room_id}:{self.from_owner_id}->{self.to_member_id}"
