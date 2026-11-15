"""Profile 模型元数据（不触碰数据库）。"""

from __future__ import annotations

from apps.profiles.models import Profile


def test_profile_table_and_fields():
    assert Profile._meta.db_table == "profiles_profile"
    assert Profile._meta.get_field("user").one_to_one is True
    assert Profile._meta.get_field("user").remote_field.on_delete.__name__ == "CASCADE"
    assert [constraint.name for constraint in Profile._meta.constraints] == [
        "uq_profile_user"
    ]
    for name in (
        "hard_answers",
        "soft_answers",
        "red_lines",
        "tags",
        "prompts",
        "dims",
        "red_lines_confirmed",
        "completeness",
        "questionnaire_version",
    ):
        assert Profile._meta.get_field(name) is not None


def test_profile_defaults():
    profile = Profile()
    assert profile.hard_answers == {}
    assert profile.soft_answers == {}
    assert profile.red_lines == []
    assert profile.tags == []
    assert profile.prompts == {}
    assert profile.dims == {}
    assert profile.red_lines_confirmed is False
    assert profile.completeness == 0
    assert profile.questionnaire_version == "v1"
