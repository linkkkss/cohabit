"""画像领域模型（docs/03 §1.4）。"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class Profile(BaseModel):
    """用户画像：1:1 用户；``dims``/``completeness`` 由服务端计算。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="用户",
    )
    hard_answers = models.JSONField("硬指标答案", default=dict, blank=True)
    soft_answers = models.JSONField("软指标答案", default=dict, blank=True)
    red_lines = models.JSONField("红线", default=list, blank=True)
    red_lines_confirmed = models.BooleanField("红线已确认", default=False)
    tags = models.JSONField("标签", default=list, blank=True)
    prompts = models.JSONField("Prompt 回答", default=dict, blank=True)
    dims = models.JSONField("六维分", default=dict, blank=True)
    completeness = models.PositiveSmallIntegerField(
        "完整度",
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    questionnaire_version = models.CharField(
        "问卷版本",
        max_length=10,
        default="v1",
    )

    class Meta:
        db_table = "profiles_profile"
        verbose_name = "画像"
        verbose_name_plural = "画像"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="uq_profile_user",
            ),
        ]

    def __str__(self) -> str:
        return f"画像({self.user_id})"
