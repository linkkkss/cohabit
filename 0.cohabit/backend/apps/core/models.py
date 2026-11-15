from django.db import models


class BaseModel(models.Model):
    """Shared timestamp fields; concrete models inherit this."""

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True
