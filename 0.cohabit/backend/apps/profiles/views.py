"""画像/问卷/公开用户 API（docs/04 §4.1 我的、§4.2 公开摘要）。"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import ContactInfo
from apps.profiles import services
from apps.profiles.api import DomainAPIView
from apps.profiles.constants import questionnaire_payload
from apps.profiles.models import Profile
from apps.profiles.serializers import (
    ContactInfoSerializer,
    ProfileSerializer,
    public_user_payload,
)


def _profile_for(user: Any) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


class ProfileMeView(DomainAPIView):
    """``GET/PUT/PATCH /api/me/profile``（docs/04 §4.1）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(ProfileSerializer(_profile_for(request.user)).data)

    def put(self, request: Request) -> Response:
        profile = services.save_profile(request.user, request.data, partial=False)
        return Response(ProfileSerializer(profile).data)

    def patch(self, request: Request) -> Response:
        profile = services.save_profile(request.user, request.data, partial=True)
        return Response(ProfileSerializer(profile).data)


class ContactMeView(DomainAPIView):
    """``GET/PUT /api/me/contact``：唯一返回本人 contact（含 show_*）的接口。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        contact, _ = ContactInfo.objects.get_or_create(user=request.user)
        return Response(ContactInfoSerializer(contact).data)

    def put(self, request: Request) -> Response:
        contact, _ = ContactInfo.objects.get_or_create(user=request.user)
        # 未提供的字段保持原值；显式 null/"" 表示清空（docs/04 §4.1）。
        serializer = ContactInfoSerializer(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request: Request) -> Response:
        return self.put(request)


class QuestionnaireView(DomainAPIView):
    """``GET /api/questionnaire``：v1 只读题目配置，登录用户可缓存。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(questionnaire_payload())


class PublicUserView(DomainAPIView):
    """``GET /api/users/:uid``：同院同性别、未被拉黑的公开摘要。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, uid: str) -> Response:
        target = services.public_profile(uid, request.user)
        return Response(public_user_payload(target))
