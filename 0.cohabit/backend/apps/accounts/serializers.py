"""accounts 序列化器：认证请求体与 UserSummary/Me 响应体（docs/04 §2、§3.1、§3.2）。"""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User

# 开发手册 D13：6 个自绘 SVG，按 uid 稳定映射；avatar_key 不入库，由 API 派生。
AVATAR_KEYS = tuple(f"avatar-0{index}" for index in range(1, 7))


def avatar_key_for(uid: str) -> str:
    try:
        index = int(uid) % len(AVATAR_KEYS)
    except (TypeError, ValueError):
        index = 0
    return AVATAR_KEYS[index]


class UserSummarySerializer(serializers.ModelSerializer):
    """公开用户摘要（docs/04 §3.1），不含 email/contact。"""

    avatar_key = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("uid", "nickname", "avatar_key", "gender", "college", "major", "grade")
        read_only_fields = fields

    def get_avatar_key(self, obj: User) -> str:
        return avatar_key_for(obj.uid)


class MeSerializer(UserSummarySerializer):
    """当前用户汇总（docs/04 §3.2/§4.1）。"""

    profile_completeness = serializers.SerializerMethodField()
    questionnaire_version = serializers.SerializerMethodField()
    room = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + (
            "role",
            "status",
            "profile_completeness",
            "questionnaire_version",
            "room",
            "unread_count",
        )
        read_only_fields = fields

    def get_profile_completeness(self, obj: User) -> int:
        from apps.profiles.me_context import profile_completeness

        return profile_completeness(obj)

    def get_questionnaire_version(self, obj: User) -> str:
        from apps.profiles.me_context import questionnaire_version

        return questionnaire_version(obj)

    def get_room(self, obj: User) -> dict[str, object] | None:
        from apps.profiles.me_context import room_summary

        return room_summary(obj)

    def get_unread_count(self, obj: User) -> int:
        from apps.profiles.me_context import unread_count

        return unread_count(obj)


class SendCodeSerializer(serializers.Serializer):
    """POST /api/auth/send-code（docs/04 §2.1）。"""

    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=("REGISTER",), default="REGISTER", required=False
    )


class RegisterSerializer(serializers.Serializer):
    """POST /api/auth/register（docs/04 §2.2）。"""

    email = serializers.EmailField(max_length=254)
    code = serializers.CharField(min_length=6, max_length=6, trim_whitespace=True)
    password = serializers.CharField(
        min_length=8, max_length=64, write_only=True, trim_whitespace=False
    )
    nickname = serializers.CharField(min_length=1, max_length=20)
    gender = serializers.ChoiceField(choices=User.Gender.choices)
    grade = serializers.IntegerField(min_value=1, max_value=5)
    college = serializers.CharField(min_length=1, max_length=50)
    major = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    invite_code = serializers.CharField(
        min_length=8, max_length=12, required=False, allow_blank=True, trim_whitespace=True
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_nickname(self, value: str) -> str:
        nickname = value.strip()
        if not nickname:
            raise serializers.ValidationError("昵称不能为空")
        return nickname

    def validate_college(self, value: str) -> str:
        college = value.strip()
        if not college:
            raise serializers.ValidationError("学院不能为空")
        return college

    def validate_major(self, value: str) -> str:
        return value.strip()

    def validate_invite_code(self, value: str) -> str:
        return value.strip().upper()

    def validate_password(self, value: str) -> str:
        email = str(self.initial_data.get("email", "")).strip().lower()
        try:
            validate_password(value, user=User(email=email))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class LoginSerializer(serializers.Serializer):
    """POST /api/auth/login（docs/04 §2.3）。"""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class MeUpdateSerializer(serializers.Serializer):
    """PUT /api/me：只允许修改基础资料的可写字段（docs/04 §4.1）。"""

    nickname = serializers.CharField(
        min_length=1, max_length=20, required=False, trim_whitespace=True
    )
    grade = serializers.IntegerField(min_value=1, max_value=5, required=False)
    college = serializers.CharField(
        min_length=1, max_length=50, required=False, trim_whitespace=True
    )
    major = serializers.CharField(
        min_length=1, max_length=50, required=False, trim_whitespace=True
    )

    def validate_nickname(self, value: str) -> str:
        nickname = value.strip()
        if not nickname:
            raise serializers.ValidationError("昵称不能为空")
        return nickname

    def validate_college(self, value: str) -> str:
        college = value.strip()
        if not college:
            raise serializers.ValidationError("学院不能为空")
        return college

    def validate_major(self, value: str) -> str:
        major = value.strip()
        if not major:
            raise serializers.ValidationError("专业不能为空")
        return major

