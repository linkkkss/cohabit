"""用户创建后的空画像/空联系方式（docs/04 §4.1、B6）。

用 ``post_save`` 而不是改 accounts 注册流程：注册事务内触发，幂等（``get_or_create``），
User 删除时由数据库级联清理。``raw=True``（loaddata）不建壳。
"""

from __future__ import annotations

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import ContactInfo
from apps.profiles.models import Profile


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="profiles.create_user_shells",
)
def create_user_shells(
    sender: type,
    instance,
    created: bool = False,
    raw: bool = False,
    **kwargs,
) -> None:
    if raw or not created:
        return
    Profile.objects.get_or_create(user=instance)
    ContactInfo.objects.get_or_create(user=instance)
