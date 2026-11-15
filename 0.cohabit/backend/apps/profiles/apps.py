from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.profiles"
    label = "profiles"
    verbose_name = "画像"

    def ready(self) -> None:
        # 注册“创建用户即建空画像/联系方式”的 post_save 信号（B6）。
        from apps.profiles import signals  # noqa: F401
