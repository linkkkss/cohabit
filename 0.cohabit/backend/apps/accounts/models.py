"""accounts 领域模型：自定义用户（docs/03 §1.3.1）。"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.models import BaseModel

UID_LENGTH = 10
UID_MAX_ATTEMPTS = 5
UID_VALIDATOR = RegexValidator(r"^\d{10}$", "UID 必须是 10 位数字")

# 邀请码生成器排除易混淆字符 0/O/1/I（docs/03 §1.3.4）；校验允许 A-Z0-9，
# 以兼容文档/seed 固定码（如 COHAB2026）。
INVITE_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
INVITE_CODE_LENGTH = 10
INVITE_CODE_PATTERN = r"^[A-Z0-9]{8,12}$"
INVITE_CODE_VALIDATOR = RegexValidator(
    INVITE_CODE_PATTERN,
    "邀请码须为 8–12 位大写字母数字",
)


def generate_invite_code(length: int = INVITE_CODE_LENGTH) -> str:
    """生成去混淆的邀请码（默认 10 位，落在 8–12 位合法区间）。"""
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(length))


def generate_uid() -> str:
    """生成 10 位数字 UID（允许前导零），如 ``0834215769``。"""
    return f"{secrets.randbelow(10**UID_LENGTH):0{UID_LENGTH}d}"


class UserManager(BaseUserManager):
    """以 email 为登录名；UID 由服务端生成，冲突时最多重试 5 次。"""

    use_in_migrations = True

    @staticmethod
    def _normalize_uid(value: object) -> str:
        """校验并规范化调用方显式传入的 UID（供 seed/测试使用）。"""
        if isinstance(value, int):
            if not 0 <= value < 10**UID_LENGTH:
                raise ValueError("UID 必须是 10 位数字")
            return f"{value:0{UID_LENGTH}d}"
        uid = str(value)
        if len(uid) != UID_LENGTH or not uid.isdigit():
            raise ValueError("UID 必须是 10 位数字")
        return uid

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> User:
        # docs/04 §注册：邮箱不区分大小写，存储前 lower()。
        email = (email or "").strip().lower()
        if not email:
            raise ValueError("email 不能为空")
        uid = extra_fields.pop("uid", None)
        if uid is not None:
            uid = self._normalize_uid(uid)
        attempts = 1 if uid is not None else UID_MAX_ATTEMPTS
        last_error: IntegrityError | None = None
        for _ in range(attempts):
            candidate = uid or generate_uid()
            user = self.model(email=email, uid=candidate, **extra_fields)
            user.set_password(password)
            try:
                # 事务保证并发下唯一约束冲突可回滚后重试。
                with transaction.atomic(using=self._db):
                    user.save(using=self._db)
            except IntegrityError as exc:
                if uid is not None or not self.model._base_manager.filter(uid=candidate).exists():
                    raise
                last_error = exc
                continue
            return user
        raise IntegrityError(f"UID 连续 {attempts} 次生成冲突，请重试") from last_error

    def get_by_natural_key(self, username: str | None) -> User:
        # docs/04 §注册：邮箱不区分大小写；存储已 lower()，查询同样归一化。
        return self.get(**{self.model.USERNAME_FIELD: (username or "").strip().lower()})

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        extra_fields.setdefault("status", self.model.Status.ACTIVE)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("超级用户必须 is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("超级用户必须 is_superuser=True")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """平台用户：email 登录、10 位数字 UID，角色/状态驱动权限。"""

    class Role(models.TextChoices):
        STUDENT = "STUDENT", "学生"
        ADMIN = "ADMIN", "管理员"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "正常"
        DISABLED = "DISABLED", "禁用"

    class Gender(models.TextChoices):
        MALE = "MALE", "男"
        FEMALE = "FEMALE", "女"

    uid = models.CharField(
        "UID",
        max_length=UID_LENGTH,
        unique=True,
        editable=False,
        default=generate_uid,
        validators=[UID_VALIDATOR],
        help_text="对外 UID，10 位数字（保留前导零）",
    )
    email = models.EmailField("邮箱", unique=True, help_text="登录名")
    nickname = models.CharField("昵称", max_length=20)
    gender = models.CharField("性别", max_length=10, choices=Gender.choices)
    grade = models.PositiveSmallIntegerField(
        "年级",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    college = models.CharField("学院", max_length=50, db_index=True)
    major = models.CharField("专业", max_length=50, blank=True, default="")
    role = models.CharField("角色", max_length=10, choices=Role.choices, default=Role.STUDENT)
    status = models.CharField("状态", max_length=10, choices=Status.choices, default=Status.ACTIVE)
    is_staff = models.BooleanField("可访问后台", default=False)
    is_active = models.BooleanField("有效", default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nickname", "gender", "college"]

    class Meta:
        db_table = "accounts_user"
        verbose_name = "用户"
        verbose_name_plural = "用户"
        swappable = "AUTH_USER_MODEL"
        indexes = [
            models.Index(fields=["college", "gender", "status"], name="idx_user_match"),
        ]

    def __str__(self) -> str:
        return f"{self.nickname}({self.uid})"

    def save(self, *args, **kwargs) -> None:
        # 兜底：Admin/工厂等绕过 create_user 的写入也必须小写存储（docs/04 §注册）。
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class InviteCode(BaseModel):
    """内测邀请码（docs/03 §1.3.4）。

    ``max_uses=0`` 表示不限次数；``used_count`` 只在注册事务内加锁递增。
    """

    code = models.CharField(
        "邀请码",
        max_length=12,
        unique=True,
        validators=[INVITE_CODE_VALIDATOR],
        help_text="8–12 位大写字母数字，如 COHAB2026；自动生成时排除 0/O/1/I",
    )
    note = models.CharField("备注", max_length=100, blank=True, default="")
    max_uses = models.PositiveSmallIntegerField("可用次数", default=1, help_text="0 表示不限次数")
    used_count = models.PositiveSmallIntegerField("已用次数", default=0)
    expires_at = models.DateTimeField("过期时间", null=True, blank=True)
    is_active = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_invite_codes",
    )

    class Meta:
        db_table = "accounts_invite_code"
        verbose_name = "邀请码"
        verbose_name_plural = "邀请码"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.code

    def is_usable(self, now=None) -> bool:
        """启用、未过期且次数未用尽；失败原因对外统一为 400 INVITE_INVALID。"""
        moment = now or timezone.now()
        if not self.is_active:
            return False
        if self.expires_at is not None and self.expires_at <= moment:
            return False
        return self.max_uses == 0 or self.used_count < self.max_uses

    def save(self, *args, **kwargs) -> None:
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)


class ContactInfo(BaseModel):
    """联系方式与可见开关（docs/03 §1.3.2），只在解锁的连接详情或本人接口返回。"""

    QQ_VALIDATOR = RegexValidator(r"^\d{5,12}$", "QQ 必须是 5–12 位数字")
    PHONE_VALIDATOR = RegexValidator(r"^1[3-9]\d{9}$", "手机号必须是 11 位中国大陆号码")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="contact_info",
    )
    qq = models.CharField(
        "QQ",
        max_length=20,
        null=True,
        blank=True,
        default=None,
        validators=[QQ_VALIDATOR],
    )
    wechat = models.CharField(
        "微信",
        max_length=40,
        null=True,
        blank=True,
        default=None,
    )
    phone = models.CharField(
        "手机号",
        max_length=20,
        null=True,
        blank=True,
        default=None,
        validators=[PHONE_VALIDATOR],
    )
    show_qq = models.BooleanField("展示 QQ", default=True)
    show_wechat = models.BooleanField("展示微信", default=True)
    show_phone = models.BooleanField("展示手机号", default=False)

    class Meta:
        db_table = "accounts_contact_info"
        verbose_name = "联系方式"
        verbose_name_plural = "联系方式"
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uq_contact_user"),
        ]

    def __str__(self) -> str:
        return f"联系方式({self.user_id})"

    def save(self, *args, **kwargs) -> None:
        # 空字符串统一存 None，便于 API 用 null 表示“清空/未填”。
        for field_name in ("qq", "wechat", "phone"):
            value = (getattr(self, field_name) or "").strip()
            setattr(self, field_name, value or None)
        super().save(*args, **kwargs)

