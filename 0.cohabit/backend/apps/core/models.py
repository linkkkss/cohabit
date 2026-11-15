from django.db import models


class BaseModel(models.Model):
    """公共字段（docs/03 §1.2）：内部主键与创建/更新时间。"""

    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True
