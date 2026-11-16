"""Django Admin 注册：自定义用户与邀请码（docs/03 §1.3.1、§1.3.4）。"""

from __future__ import annotations

import csv

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.http import HttpResponse
from django.utils import timezone

from apps.core.audit import write_audit

from . import lifecycle
from .models import ContactInfo, InviteCode, User, generate_invite_code

# 导出白名单：不含 email / password / 联系方式（docs/06 FA-08、S-03）。
USER_EXPORT_COLUMNS = (
    "uid",
    "nickname",
    "gender",
    "grade",
    "college",
    "major",
    "role",
    "status",
    "is_staff",
    "is_active",
    "created_at",
)


def _csv_response(filename: str, header: tuple[str, ...], rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # Excel 中文兼容
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


def _request_id(request) -> str:
    value = request.headers.get("X-Request-Id") or request.META.get("HTTP_X_REQUEST_ID")
    return str(value or "")[:64]


class UserCreationForm(BaseUserCreationForm):
    """后台新增用户：email 作为登录名，UID 由服务端生成。"""

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = (
            "email",
            "nickname",
            "gender",
            "grade",
            "college",
            "major",
            "role",
            "status",
            "is_staff",
            "is_active",
        )


class UserChangeForm(BaseUserChangeForm):
    """后台编辑用户：密码仅展示哈希，UID 只读。"""

    class Meta(BaseUserChangeForm.Meta):
        model = User
        fields = "__all__"


class InviteCodeAdminForm(forms.ModelForm):
    """邀请码表单：code 留空时自动生成不冲突的去混淆码。"""

    code = forms.CharField(
        label="邀请码",
        required=False,
        max_length=12,
        help_text="留空自动生成 10 位邀请码；内测码可直接填 COHAB2026",
    )

    class Meta:
        model = InviteCode
        fields = "__all__"

    def clean_code(self) -> str:
        code = str(self.cleaned_data.get("code") or "").strip().upper()
        if code:
            return code
        for _ in range(10):
            candidate = generate_invite_code()
            if not InviteCode.objects.filter(code=candidate).exists():
                return candidate
        raise forms.ValidationError("邀请码自动生成冲突，请重试")


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    form = InviteCodeAdminForm
    list_display = (
        "code",
        "note",
        "max_uses",
        "used_count",
        "remaining_uses",
        "expires_at",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "note")
    ordering = ("-created_at",)
    readonly_fields = ("used_count", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("code", "note", "is_active")}),
        ("使用限制", {"fields": ("max_uses", "used_count", "expires_at")}),
        ("审计", {"fields": ("created_by", "created_at", "updated_at")}),
    )
    actions = ("enable_codes", "disable_codes")

    @admin.display(description="剩余次数")
    def remaining_uses(self, obj: InviteCode) -> str | int:
        if obj.max_uses == 0:
            return "不限"
        return max(obj.max_uses - obj.used_count, 0)

    def save_model(self, request, obj: InviteCode, form, change: bool) -> None:
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="启用所选邀请码")
    def enable_codes(self, request, queryset):
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"已启用 {updated} 个邀请码")

    @admin.action(description="停用所选邀请码")
    def disable_codes(self, request, queryset):
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"已停用 {updated} 个邀请码")


@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    """联系方式只读：Admin 不展开明文敏感值（docs/03 §1.3.2）。"""

    list_display = ("user", "has_qq", "has_wechat", "has_phone", "updated_at")
    list_filter = ("show_qq", "show_wechat", "show_phone")
    search_fields = ("user__uid", "user__email", "user__nickname")
    ordering = ("-updated_at",)
    readonly_fields = (
        "user",
        "qq",
        "wechat",
        "phone",
        "show_qq",
        "show_wechat",
        "show_phone",
        "created_at",
        "updated_at",
    )

    @admin.display(boolean=True, description="已填 QQ")
    def has_qq(self, obj: ContactInfo) -> bool:
        return bool(obj.qq)

    @admin.display(boolean=True, description="已填微信")
    def has_wechat(self, obj: ContactInfo) -> bool:
        return bool(obj.wechat)

    @admin.display(boolean=True, description="已填手机")
    def has_phone(self, obj: ContactInfo) -> bool:
        return bool(obj.phone)

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = (
        "uid",
        "email",
        "nickname",
        "role",
        "status",
        "college",
        "gender",
        "grade",
        "is_staff",
        "is_active",
        "created_at",
    )
    list_filter = ("role", "status", "gender", "college", "is_staff", "is_active")
    search_fields = ("uid", "email", "nickname", "college", "major")
    ordering = ("-created_at",)
    readonly_fields = ("uid", "last_login", "created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")
    actions = ("disable_users", "export_users_csv")

    fieldsets = (
        (None, {"fields": ("uid", "email", "password")}),
        ("个人信息", {"fields": ("nickname", "gender", "grade", "college", "major")}),
        ("角色与状态", {"fields": ("role", "status", "is_staff", "is_active", "is_superuser")}),
        ("权限", {"fields": ("groups", "user_permissions")}),
        ("时间", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nickname",
                    "gender",
                    "grade",
                    "college",
                    "major",
                    "role",
                    "status",
                    "is_staff",
                    "is_active",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @admin.action(description="禁用所选用户（级联清理在途请求/寝室）")
    def disable_users(self, request, queryset):
        disabled = 0
        skipped = 0
        for user in queryset.select_related("contact_info").order_by("pk"):
            if user.pk == getattr(request.user, "pk", None):
                skipped += 1
                self.message_user(request, "不能禁用当前登录账号。", messages.ERROR)
                continue
            if user.status == User.Status.DISABLED and not user.is_active:
                skipped += 1
                continue
            try:
                lifecycle.disable_account(
                    user,
                    actor=request.user,
                    request_id=_request_id(request),
                )
            except Exception as exc:  # noqa: BLE001 - 后台批量动作逐条报告失败
                self.message_user(
                    request,
                    f"用户 {user.uid} 禁用失败：{exc}",
                    messages.ERROR,
                )
                continue
            disabled += 1
        if disabled:
            self.message_user(request, f"已禁用 {disabled} 个账号（已级联清理）。")
        elif not skipped:
            self.message_user(request, "没有可禁用的账号。", messages.WARNING)
        elif skipped:
            self.message_user(request, f"跳过 {skipped} 个账号。", messages.WARNING)

    @admin.action(description="导出所选用户 CSV（不含邮箱/密码/联系方式）")
    def export_users_csv(self, request, queryset):
        users = queryset.order_by("pk")
        rows = (
            (
                user.uid,
                user.nickname,
                user.get_gender_display(),
                user.grade,
                user.college,
                user.major,
                user.get_role_display(),
                user.get_status_display(),
                user.is_staff,
                user.is_active,
                user.created_at.isoformat() if user.created_at else "",
            )
            for user in users.iterator()
        )
        write_audit(
            "AUDIT_EXPORTED",
            "user",
            None,
            actor=request.user,
            meta={
                "model": "User",
                "count": users.count(),
                "columns": list(USER_EXPORT_COLUMNS),
            },
            request_id=_request_id(request),
        )
        return _csv_response("users.csv", USER_EXPORT_COLUMNS, rows)
