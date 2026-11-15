"""DRF-wide API conventions: pagination shape and error envelope."""
from __future__ import annotations

from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.views import exception_handler as drf_exception_handler


class StandardPagination(PageNumberPagination):
    """The paginated shape frozen in docs/04: count/next/previous/results."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


def _default_message(data: Any) -> str:
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, (list, tuple)) and value:
                return str(value[0])
            if isinstance(value, str):
                return value
    if isinstance(data, (list, tuple)) and data:
        return str(data[0])
    return "请求未完成"


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Any:
    """Wrap DRF exceptions as ``{code, message, detail}``."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    raw_detail = response.data
    code = getattr(exc, "default_code", "error")
    response.data = {
        "code": str(code).upper(),
        "message": _default_message(raw_detail),
        "detail": raw_detail,
    }
    return response
