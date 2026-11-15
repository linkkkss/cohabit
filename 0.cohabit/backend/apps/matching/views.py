"""匹配 API（docs/04 §4.2：匹配列表/详情/评分）。"""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from config.api import StandardPagination

from apps.accounts.exceptions import ApiError
from apps.matching import services
from apps.matching.serializers import match_score_payload
from apps.matching.throttling import enforce_score_limit
from apps.profiles.api import DomainAPIView


def _parse_min_score(request: Request) -> int | None:
    raw = request.query_params.get("min_score")
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={"fields": {"min_score": "min_score 必须是 0–100 的整数。"}},
        ) from None
    if value < 0 or value > 100:
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={"fields": {"min_score": "min_score 必须是 0–100 的整数。"}},
        )
    return value


def _parse_tags(request: Request) -> list[str]:
    raw = request.query_params.get("tags")
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


class MatchListView(DomainAPIView):
    """``GET /api/match``：候选池算分 + 过滤 + 分页（docs/04 §4.2）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        major = (request.query_params.get("major") or "").strip()
        tags = _parse_tags(request)
        min_score = _parse_min_score(request)

        items = services.match_list(request.user)
        if major:
            items = [item for item in items if item["user"].major == major]
        if tags:
            items = [
                item
                for item in items
                if set(tags).issubset({str(tag) for tag in item["profile"].tags or []})
            ]
        if min_score is not None:
            items = [item for item in items if int(item["match"]["score"]) >= min_score]

        results = [
            match_score_payload(item["user"], item["profile"], item["match"])
            for item in items
        ]
        paginator = StandardPagination()
        page = paginator.paginate_queryset(results, request, view=self)
        if page is None:
            return Response(results)
        return paginator.get_paginated_response(page)


class MatchDetailView(DomainAPIView):
    """``GET /api/match/:uid``：单目标匹配详情。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, uid: str) -> Response:
        data = services.score_target(request.user, uid)
        return Response(match_score_payload(data["target"], data["profile"], data["match"]))


class MatchScoreView(DomainAPIView):
    """``POST /api/match/:uid/score``：重算单目标分数（限频 60/h）。"""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, uid: str) -> Response:
        enforce_score_limit(request.user)
        data = services.score_target(request.user, uid)
        return Response(match_score_payload(data["target"], data["profile"], data["match"]))
