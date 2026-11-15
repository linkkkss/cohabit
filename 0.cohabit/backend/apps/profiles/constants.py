"""问卷 v1 的只读常量（docs/03 §2–§7）。

本模块只放数据，不放业务逻辑：
- 11 道硬指标、6 道软指标、9 条红线、42 个标签、6 个 prompt；
- 六维名称与权重；
- 各类上限与问卷版本。

所有文案与 docs/03 冻结版本保持一致，前端通过 ``questionnaire_payload()``
取值，不在前端硬编码。
"""

from __future__ import annotations

from typing import Any, Final

QUESTIONNAIRE_VERSION: Final = "v1"
SUPPORTED_QUESTIONNAIRE_VERSIONS: Final = frozenset({"v1"})
QUESTIONNAIRE_VERSION_MAX_LENGTH: Final = 10

DIMENSIONS: Final = ("sleep", "clean", "social", "noise", "boundary", "spend")
DIMENSION_LABELS: Final = {
    "sleep": "作息",
    "clean": "整洁",
    "social": "社交",
    "noise": "声音",
    "boundary": "边界",
    "spend": "开销",
}
# docs/03 §8.4：权重和 = 100。
DIMENSION_WEIGHTS: Final = {
    "sleep": 20,
    "clean": 20,
    "social": 15,
    "noise": 15,
    "boundary": 15,
    "spend": 15,
}

HARD_ANSWER_COUNT: Final = 11
SOFT_ANSWER_COUNT: Final = 6
MAX_RED_LINES: Final = 9
MAX_TAGS: Final = 8
MIN_TAGS_FOR_COMPLETENESS: Final = 3
MAX_PROMPTS: Final = 3
MIN_PROMPTS_FOR_COMPLETENESS: Final = 2
PROMPT_MAX_LENGTH: Final = 120
PROMPT_MAX_LINES: Final = 3
SOFT_MIN: Final = 1
SOFT_MAX: Final = 5
PROFILE_MAX_PAYLOAD_BYTES: Final = 16 * 1024
RED_LINE_CONFLICT_SCORE_CAP: Final = 59
MAX_RED_CONFLICT_PENALTY: Final = 30
RED_PENALTY_PER_CONFLICT: Final = 15
MAX_TAG_BONUS: Final = 6
TAG_BONUS_PER_COMMON_TAG: Final = 2

# --- 硬指标（docs/03 §3） --------------------------------------------------
# ``dimension`` 表示该题参与哪个维度的硬指标分；``None`` 表示不进入六维。
# ``red_line`` 表示该题可被哪条红线引用（仅用于展示/校验，不参与计算）。
HARD_QUESTIONS: Final[tuple[dict[str, Any], ...]] = (
    {
        "key": "smoke",
        "title": "你吸烟吗？",
        "group": "生活习惯",
        "dimension": "boundary",
        "red_line": "smoke",
        "options": (
            {"value": "no", "label": "不吸", "score": 100},
            {"value": "sometimes", "label": "偶尔", "score": 50},
            {"value": "yes", "label": "经常", "score": 0},
        ),
    },
    {
        "key": "sleep_time",
        "title": "你通常几点入睡？",
        "group": "作息",
        "dimension": "sleep",
        "red_line": None,
        "options": (
            {"value": "before23", "label": "23:00 前", "score": 100},
            {"value": "23_00", "label": "23:00–00:00", "score": 70},
            {"value": "00_01", "label": "00:00–01:00", "score": 35},
            {"value": "after01", "label": "01:00 后", "score": 0},
        ),
    },
    {
        "key": "wake_time",
        "title": "你通常几点起床？",
        "group": "作息",
        "dimension": "sleep",
        "red_line": None,
        "options": (
            {"value": "before7", "label": "7:00 前", "score": 100},
            {"value": "7_8", "label": "7:00–8:00", "score": 75},
            {"value": "8_9", "label": "8:00–9:00", "score": 50},
            {"value": "after9", "label": "9:00 后", "score": 0},
        ),
    },
    {
        "key": "late_return",
        "title": "你凌晨（0 点后）归寝的频率？",
        "group": "作息",
        "dimension": "sleep",
        "red_line": "late_return",
        "options": (
            {"value": "never", "label": "从不", "score": 100},
            {"value": "rarely", "label": "很少（每月 ≤2 次）", "score": 70},
            {"value": "sometimes", "label": "有时（每周 1–2 次）", "score": 35},
            {"value": "often", "label": "经常（每周 ≥3 次）", "score": 0},
        ),
    },
    {
        "key": "snore",
        "title": "你睡觉打鼾吗？",
        "group": "作息",
        "dimension": "noise",
        "red_line": "snore",
        "options": (
            {"value": "no", "label": "不打鼾", "score": 100},
            {"value": "mild", "label": "偶尔/轻微", "score": 50},
            {"value": "yes", "label": "经常/明显", "score": 0},
        ),
    },
    {
        "key": "pet",
        "title": "你对宠物的态度？",
        "group": "生活习惯",
        "dimension": "boundary",
        "red_line": "pet",
        "options": (
            {"value": "no_pet", "label": "不接受宠物", "score": 0},
            {"value": "ok", "label": "可以接受", "score": 50},
            {"value": "has_pet", "label": "我自己养宠物", "score": 100},
        ),
    },
    {
        "key": "visitor_freq",
        "title": "你带朋友回寝的频率？",
        "group": "空间与整洁",
        "dimension": "boundary",
        "red_line": "visitor_freq",
        "options": (
            {"value": "never", "label": "几乎不带", "score": 100},
            {"value": "rarely", "label": "很少", "score": 70},
            {"value": "sometimes", "label": "有时", "score": 35},
            {"value": "often", "label": "经常", "score": 0},
        ),
    },
    {
        "key": "alcohol",
        "title": "你饮酒的频率？",
        "group": "生活习惯",
        "dimension": None,
        "red_line": "alcohol",
        "options": (
            {"value": "never", "label": "不喝", "score": None},
            {"value": "social", "label": "社交场合偶尔", "score": None},
            {"value": "often", "label": "经常", "score": None},
        ),
    },
    {
        "key": "game_noise",
        "title": "你打游戏会外放吗？",
        "group": "生活习惯",
        "dimension": "noise",
        "red_line": "game_noise",
        "options": (
            {"value": "never", "label": "不外放", "score": 100},
            {"value": "headphones", "label": "基本戴耳机", "score": 80},
            {"value": "sometimes", "label": "偶尔外放", "score": 40},
            {"value": "often", "label": "经常外放", "score": 0},
        ),
    },
    {
        "key": "ac_temp",
        "title": "你偏好的空调温度？",
        "group": "空间与整洁",
        "dimension": None,
        "red_line": "ac_dc",
        "options": (
            {"value": "cool", "label": "偏冷（≤24°C）", "score": 0},
            {"value": "medium", "label": "适中（25–26°C）", "score": 50},
            {"value": "warm", "label": "偏暖（≥27°C）", "score": 100},
        ),
    },
    {
        "key": "clean_freq",
        "title": "你打扫寝室的频率？",
        "group": "空间与整洁",
        "dimension": "clean",
        "red_line": "clean_low",
        "options": (
            {"value": "daily", "label": "每天/几乎每天", "score": 100},
            {"value": "2_3_week", "label": "每周 2–3 次", "score": 70},
            {"value": "weekly", "label": "每周 1 次", "score": 40},
            {"value": "rarely", "label": "很少/看心情", "score": 0},
        ),
    },
)

HARD_QUESTION_ORDER: Final = tuple(q["key"] for q in HARD_QUESTIONS)
HARD_QUESTION_MAP: Final = {q["key"]: q for q in HARD_QUESTIONS}
HARD_OPTION_MAP: Final = {
    q["key"]: {o["value"]: o for o in q["options"]} for q in HARD_QUESTIONS
}
HARD_SCORE_MAP: Final = {
    key: {
        option["value"]: option["score"]
        for option in question["options"]
        if option["score"] is not None
    }
    for key, question in HARD_QUESTION_MAP.items()
}
# 展示分组（docs/03 §3.1 的顺序）。
HARD_GROUPS: Final = tuple(
    dict.fromkeys(question["group"] for question in HARD_QUESTIONS)
)

# --- 软指标（docs/03 §4） --------------------------------------------------
SOFT_QUESTIONS: Final[tuple[dict[str, Any], ...]] = (
    {
        "key": "clean",
        "title": "你对寝室整洁的要求有多高？",
        "dimension": "clean",
        "labels": {1: "很随意", 3: "中等", 5: "很高"},
    },
    {
        "key": "social",
        "title": "你希望寝室的社交热度？",
        "dimension": "social",
        "labels": {1: "安静独处", 3: "偶尔一起", 5: "经常热闹"},
    },
    {
        "key": "noise",
        "title": "你对声音的敏感度？",
        "dimension": "noise",
        "labels": {1: "不敏感", 3: "一般", 5: "很敏感"},
    },
    {
        "key": "boundary",
        "title": "你的边界感/隐私需求？",
        "dimension": "boundary",
        "labels": {1: "很随意", 3: "中等", 5: "很强"},
    },
    {
        "key": "spend",
        "title": "你对公共开销分摊的意愿？",
        "dimension": "spend",
        "labels": {1: "尽量省", 3: "适中", 5: "愿意多分摊"},
    },
    {
        "key": "sleep_regular",
        "title": "你的作息规律程度？",
        "dimension": "sleep",
        "labels": {1: "很不规律", 3: "一般", 5: "很规律"},
    },
)
SOFT_QUESTION_ORDER: Final = tuple(q["key"] for q in SOFT_QUESTIONS)
SOFT_QUESTION_MAP: Final = {q["key"]: q for q in SOFT_QUESTIONS}

# --- 红线（docs/03 §5） ----------------------------------------------------
RED_LINES: Final[tuple[dict[str, Any], ...]] = (
    {
        "id": "smoke",
        "label": "吸烟",
        "description": "我不能接受室友吸烟",
        "question_key": "smoke",
        "trigger_values": ("sometimes", "yes"),
        "message": "对方有吸烟习惯，与你的红线冲突。",
    },
    {
        "id": "snore",
        "label": "打鼾",
        "description": "我不能接受室友打鼾",
        "question_key": "snore",
        "trigger_values": ("mild", "yes"),
        "message": "对方可能打鼾，与你的红线冲突。",
    },
    {
        "id": "late_return",
        "label": "凌晨归寝",
        "description": "我不能接受室友经常凌晨回来",
        "question_key": "late_return",
        "trigger_values": ("sometimes", "often"),
        "message": "对方经常凌晨归寝，与你的红线冲突。",
    },
    {
        "id": "pet",
        "label": "宠物",
        "description": "我不能接受室友养宠物",
        "question_key": "pet",
        "trigger_values": ("has_pet",),
        "message": "对方养宠物，与你的红线冲突。",
    },
    {
        "id": "alcohol",
        "label": "饮酒",
        "description": "我不能接受室友饮酒",
        "question_key": "alcohol",
        "trigger_values": ("social", "often"),
        "message": "对方有饮酒习惯，与你的红线冲突。",
    },
    {
        "id": "game_noise",
        "label": "游戏外放",
        "description": "我不能接受室友游戏外放",
        "question_key": "game_noise",
        "trigger_values": ("sometimes", "often"),
        "message": "对方打游戏会外放，与你的红线冲突。",
    },
    {
        "id": "visitor_freq",
        "label": "频繁访客",
        "description": "我不能接受室友经常带人回寝",
        "question_key": "visitor_freq",
        "trigger_values": ("sometimes", "often"),
        "message": "对方经常带朋友回寝，与你的红线冲突。",
    },
    {
        "id": "ac_dc",
        "label": "空调温度",
        "description": "我对空调温度差异敏感",
        "question_key": "ac_temp",
        "trigger_values": (),
        "message": "你们对空调温度的偏好差异较大。",
    },
    {
        "id": "clean_low",
        "label": "卫生容忍低",
        "description": "我不能接受室友打扫频率低",
        "question_key": "clean_freq",
        "trigger_values": ("weekly", "rarely"),
        "message": "对方打扫频率较低，与你的红线冲突。",
    },
)
RED_LINE_ORDER: Final = tuple(item["id"] for item in RED_LINES)
RED_LINE_MAP: Final = {item["id"]: item for item in RED_LINES}
AC_TEMP_CONFLICT_THRESHOLD: Final = 50

# --- 标签（docs/03 §6） ----------------------------------------------------
TAG_GROUPS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("作息", ("早睡早起", "夜猫子", "午睡党", "作息规律", "周末补觉", "闹钟困难户")),
    ("整洁", ("洁癖", "随手收拾", "每周打扫", "物品归位", "公共区容忍", "需要提醒")),
    ("社交", ("社恐", "社牛", "安静独处", "喜欢聚餐", "游戏搭子", "自习搭子", "一起运动")),
    (
        "兴趣",
        ("猫派", "狗派", "二次元", "电影迷", "音乐现场", "阅读", "摄影", "徒步"),
    ),
    (
        "生活",
        ("咖啡续命", "奶茶党", "外卖常客", "食堂党", "健身", "熬夜赶due", "早起学习"),
    ),
    (
        "边界",
        (
            "借东西先问",
            "不喜欢借",
            "访客提前说",
            "不接受访客",
            "耳机党",
            "外放党",
            "需要私人空间",
            "可以分享",
        ),
    ),
)
TAG_ORDER: Final = tuple(tag for _, tags in TAG_GROUPS for tag in tags)
TAG_SET: Final = frozenset(TAG_ORDER)
TAG_GROUP_MAP: Final = {
    tag: group for group, tags in TAG_GROUPS for tag in tags
}

# --- Prompt（docs/03 §7） --------------------------------------------------
PROMPTS: Final[tuple[dict[str, Any], ...]] = (
    {
        "key": "weekend",
        "title": "周末我更愿意……",
        "placeholder": "例如：在图书馆待一天，晚上打游戏",
        "max_length": PROMPT_MAX_LENGTH,
        "order": 1,
    },
    {
        "key": "small_thing",
        "title": "关于我的一件小事：……",
        "placeholder": "例如：每天必须喝一杯冰美式",
        "max_length": PROMPT_MAX_LENGTH,
        "order": 2,
    },
    {
        "key": "vibe",
        "title": "理想的寝室氛围是……",
        "placeholder": "例如：能互相借充电线，也能各戴耳机",
        "max_length": PROMPT_MAX_LENGTH,
        "order": 3,
    },
    {
        "key": "cannot_accept",
        "title": "我最不能接受室友……",
        "placeholder": "例如：凌晨外放、不打招呼带人回来",
        "max_length": PROMPT_MAX_LENGTH,
        "order": 4,
    },
    {
        "key": "visitor_expect",
        "title": "如果室友带朋友回来，我希望……",
        "placeholder": "例如：提前半天说，且不要太晚",
        "max_length": PROMPT_MAX_LENGTH,
        "order": 5,
    },
    {
        "key": "sleep_summary",
        "title": "用一句话介绍我的作息：……",
        "placeholder": "例如：12 点睡 7 点半起，周末补觉",
        "max_length": PROMPT_MAX_LENGTH,
        "order": 6,
    },
)
PROMPT_ORDER: Final = tuple(item["key"] for item in PROMPTS)
PROMPT_MAP: Final = {item["key"]: item for item in PROMPTS}


def questionnaire_payload() -> dict[str, Any]:
    """返回 ``GET /api/questionnaire`` 所需的完整只读结构（docs/04 §3.5）。"""
    return {
        "version": QUESTIONNAIRE_VERSION,
        "hard": [
            {
                "key": q["key"],
                "title": q["title"],
                "group": q["group"],
                "options": [
                    {
                        "value": option["value"],
                        "label": option["label"],
                        "score": option["score"],
                    }
                    for option in q["options"]
                ],
            }
            for q in HARD_QUESTIONS
        ],
        "soft": [
            {
                "key": q["key"],
                "title": q["title"],
                "min": SOFT_MIN,
                "max": SOFT_MAX,
                "labels": {str(k): v for k, v in q["labels"].items()},
            }
            for q in SOFT_QUESTIONS
        ],
        "red_lines": [
            {
                "id": item["id"],
                "label": item["label"],
                "description": item["description"],
            }
            for item in RED_LINES
        ],
        "tags": [
            {"group": group, "name": tag} for group, tags in TAG_GROUPS for tag in tags
        ],
        "prompts": [
            {
                "key": item["key"],
                "title": item["title"],
                "placeholder": item["placeholder"],
                "max_length": item["max_length"],
            }
            for item in PROMPTS
        ],
    }


def tag_sort_key(tag: str) -> int:
    """按 ``TAG_ORDER`` 返回排序键；未知标签排到最后。"""
    try:
        return TAG_ORDER.index(tag)
    except ValueError:
        return len(TAG_ORDER)


def red_line_sort_key(red_line_id: str) -> int:
    """按 ``RED_LINE_ORDER`` 返回排序键；未知 id 排到最后。"""
    try:
        return RED_LINE_ORDER.index(red_line_id)
    except ValueError:
        return len(RED_LINE_ORDER)
