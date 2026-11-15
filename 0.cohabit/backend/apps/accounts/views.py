"""认证 API（docs/04 §2）与 /api/me（docs/04 §4.1）。"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import conf, services
from apps.accounts.exceptions import ApiError, accounts_exception_handler
from apps.accounts.serializers import (
    LoginSerializer,
    MeSerializer,
    MeUpdateSerializer,
    RegisterSerializer,
    SendCodeSerializer,
)


class AccountsAPIView(APIView):
    """使用 accounts 的异常出口，把错误统一成 docs/04 §1.6 的信封。"""

    def get_exception_handler(self) -> Any:
        return accounts_exception_handler


def _client_ip(request: Request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class SendCodeView(AccountsAPIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = SendCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        dev_code = services.send_verification_code(email)
        if dev_code is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"dev_code": dev_code})


class RegisterView(AccountsAPIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.register_user(serializer.validated_data, client_ip=_client_ip(request))
        access, refresh = services.issue_tokens(user)
        response = Response(
            {
                "user": MeSerializer(user).data,
                "access": access,
                "expires_in": conf.access_expires_in(),
            },
            status=status.HTTP_201_CREATED,
        )
        services.attach_refresh_cookie(response, refresh)
        return response


class LoginView(AccountsAPIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.login_user(
            serializer.validated_data["email"],
            serializer.validated_data["password"],
            client_ip=_client_ip(request),
        )
        access, refresh = services.issue_tokens(user)
        response = Response(
            {
                "user": MeSerializer(user).data,
                "access": access,
                "expires_in": conf.access_expires_in(),
            }
        )
        services.attach_refresh_cookie(response, refresh)
        return response


class RefreshView(AccountsAPIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        if not conf.request_origin_allowed(request.META):
            raise ApiError("FORBIDDEN", status_code=status.HTTP_403_FORBIDDEN)
        access, refresh = services.refresh_session(request.COOKIES.get(conf.COOKIE_NAME))
        response = Response({"access": access, "expires_in": conf.access_expires_in()})
        services.attach_refresh_cookie(response, refresh)
        return response


class LogoutView(AccountsAPIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        if not conf.request_origin_allowed(request.META):
            raise ApiError("FORBIDDEN", status_code=status.HTTP_403_FORBIDDEN)
        services.logout_session(request.COOKIES.get(conf.COOKIE_NAME))
        response = Response(status=status.HTTP_204_NO_CONTENT)
        services.clear_refresh_cookie(response)
        return response


ME_WRITABLE_FIELDS = frozenset({"nickname", "grade", "college", "major"})
ME_PROTECTED_FIELDS = ("email", "uid", "role", "status")


def _field_errors(mapping: dict[str, dict[str, str]]) -> dict[str, Any]:
    return {"fields": mapping}


class MeView(AccountsAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)

    def put(self, request: Request) -> Response:
        payload = request.data
        if not isinstance(payload, dict):
            raise ApiError(
                "VALIDATION_ERROR",
                detail=_field_errors(
                    {"body": {"code": "VALIDATION_ERROR", "message": "请求体必须是 JSON 对象。"}}
                ),
            )
        if "gender" in payload:
            raise ApiError("GENDER_IMMUTABLE", status_code=status.HTTP_403_FORBIDDEN)
        protected = [field for field in ME_PROTECTED_FIELDS if field in payload]
        if protected:
            raise ApiError(
                "VALIDATION_ERROR",
                detail=_field_errors(
                    {
                        field: {"code": "FIELD_IMMUTABLE", "message": "该字段不可修改。"}
                        for field in protected
                    }
                ),
            )
        unknown = sorted(set(payload) - ME_WRITABLE_FIELDS)
        if unknown:
            raise ApiError(
                "VALIDATION_ERROR",
                detail=_field_errors(
                    {
                        field: {"code": "UNKNOWN_FIELD", "message": "存在未知字段。"}
                        for field in unknown
                    }
                ),
            )

        serializer = MeUpdateSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        updates = dict(serializer.validated_data)
        if updates:
            for field, value in updates.items():
                setattr(request.user, field, value)
            request.user.save(update_fields=[*updates.keys(), "updated_at"])
        return Response(MeSerializer(request.user).data)

