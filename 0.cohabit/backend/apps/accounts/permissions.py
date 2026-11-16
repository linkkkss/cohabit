"""可复用的 API 权限（docs/02 §1.1 守卫链）。

学生端组寝写操作只允许 ``role=STUDENT`` 的账号执行；GET/HEAD/OPTIONS
保持可读，Admin/staff 即使持有有效 token 也不能代替学生 confirm/accept。
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .exceptions import ApiError
from .models import User

STUDENT_WRITE_FORBIDDEN_MESSAGE = "仅学生账号可执行组寝操作。"


class IsStudentOrReadOnly(BasePermission):
    """放行安全方法；非安全方法要求当前用户是学生。

    与 ``IsAuthenticated`` 组合使用（放在其后），未登录请求仍返回 401；
    已登录的 Admin/staff 在进入 service 之前直接得到 403 ``FORBIDDEN``，
    因此不能用不存在/非法的资源 id 探测 404。
    """

    message = STUDENT_WRITE_FORBIDDEN_MESSAGE

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            # 交给 DRF 的 permission_denied 按认证器状态返回 401。
            return False
        if getattr(user, "role", None) == User.Role.STUDENT:
            return True
        raise ApiError(
            "FORBIDDEN",
            STUDENT_WRITE_FORBIDDEN_MESSAGE,
            status_code=403,
        )
