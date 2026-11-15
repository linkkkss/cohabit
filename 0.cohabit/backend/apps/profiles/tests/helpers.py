"""纯函数测试共用构造器（不访问数据库）。"""

from __future__ import annotations

from types import SimpleNamespace

from apps.profiles.constants import (
    HARD_QUESTION_MAP,
    PROMPT_ORDER,
    SOFT_QUESTION_ORDER,
    TAG_ORDER,
)


def make_user(**overrides):
    values = {
        "uid": "0000000001",
        "nickname": "小明",
        "gender": "MALE",
        "grade": 2,
        "college": "计算机学院",
        "major": "软件工程",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def full_hard(**overrides) -> dict[str, str]:
    answers = {
        key: question["options"][0]["value"]
        for key, question in HARD_QUESTION_MAP.items()
    }
    answers.update(overrides)
    return answers


def full_soft(value: int = 3, **overrides) -> dict[str, int]:
    answers = {key: value for key in SOFT_QUESTION_ORDER}
    answers.update(overrides)
    return answers


def full_tags(count: int = 3) -> list[str]:
    return list(TAG_ORDER[:count])


def full_prompts(count: int = 2) -> dict[str, str]:
    return {key: f"回答 {key}" for key in PROMPT_ORDER[:count]}


def full_payload() -> dict:
    return {
        "hard_answers": full_hard(),
        "soft_answers": full_soft(),
        "red_lines": ["smoke", "pet"],
        "red_lines_confirmed": True,
        "tags": full_tags(),
        "prompts": full_prompts(),
        "questionnaire_version": "v1",
    }
