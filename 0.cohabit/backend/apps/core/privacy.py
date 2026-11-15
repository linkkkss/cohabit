"""通知 payload / 审计 meta 的隐私护栏（docs/02 §8.1、§9.1，docs/03 §9.4）。

通知与审计会进入列表、Admin 与导出，属于 docs/04 §1.7 的硬性隐私边界：
只允许 id、枚举、计数、时间、昵称、房间号等非敏感字段。本模块在写入前拒绝
联系方式、邮箱、真名、凭据与请求元数据等字段，避免业务代码误传后落库。

这里只按 **字段名** 做静态校验，不扫描字段值：昵称本身是用户输入（如
``nickname="a@b.com"``），按值扫描会误伤并对业务事务造成不必要的回滚。
"""

from __future__ import annotations

import re
from typing import Any

# 精确匹配（规范化后：小写、非字母数字转下划线）。
FORBIDDEN_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "qq",
        "wechat",
        "weixin",
        "wechat_id",
        "wxid",
        "phone",
        "phone_number",
        "mobile",
        "tel",
        "email",
        "mail",
        "contact",
        "contact_info",
        "real_name",
        "realname",
        "true_name",
        "truename",
        "id_card",
        "id_number",
        "token",
        "access_token",
        "refresh_token",
        "jwt",
        "password",
        "passwd",
        "session_id",
        "ip",
        "ip_address",
        "user_agent",
        "useragent",
    }
)

# 后缀匹配：覆盖 user_email / contact_phone / refresh_token 等组合键。
FORBIDDEN_KEY_SUFFIXES: frozenset[str] = frozenset(
    {
        "qq",
        "wechat",
        "weixin",
        "phone",
        "mobile",
        "email",
        "token",
        "password",
        "real_name",
        "truename",
        "id_card",
        "contact",
    }
)

_NON_WORD = re.compile(r"[^a-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class PayloadNotPublicError(ValueError):
    """payload/meta 含有不允许对外持久化的敏感字段。"""


def normalize_key(key: Any) -> str:
    """把字段名规范化为小写 snake_case，用于稳定匹配。

    ``userEmail`` / ``User-Email`` 都会归一为 ``user_email``，避免驼峰写法绕过
    后缀匹配。
    """
    text = _CAMEL_BOUNDARY.sub("_", str(key).strip())
    return _NON_WORD.sub("_", text.lower()).strip("_")


def is_forbidden_key(key: Any) -> bool:
    """判断单个字段名是否属于隐私禁区（``user_email`` 之类的组合键也命中）。"""
    normalized = normalize_key(key)
    if normalized in FORBIDDEN_PAYLOAD_KEYS:
        return True
    return any(
        normalized == suffix or normalized.endswith(f"_{suffix}")
        for suffix in FORBIDDEN_KEY_SUFFIXES
    )


def assert_public_payload(payload: Any, *, where: str = "payload") -> None:
    """校验 ``payload``/``meta`` 为 JSON 对象且不含敏感字段。

    允许嵌套对象；``None`` 视为空对象。校验失败抛
    :class:`PayloadNotPublicError`（``ValueError`` 子类），由调用方的业务事务
    回滚——通知/审计写入失败必须让业务动作整体失败（docs/02 §8.1）。
    """

    if payload is None:
        return
    if not isinstance(payload, dict):
        raise PayloadNotPublicError(f"{where} 必须是 JSON 对象")
    for key, value in payload.items():
        if is_forbidden_key(key):
            raise PayloadNotPublicError(f"{where} 不允许包含敏感字段：{key!r}")
        if isinstance(value, dict):
            assert_public_payload(value, where=where)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, dict):
                    assert_public_payload(item, where=where)
