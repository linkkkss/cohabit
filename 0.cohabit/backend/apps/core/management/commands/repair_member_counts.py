"""``repair_member_counts``：``repair_member_count`` 的文档别名（docs/02 §1635 cron 表）。"""

from __future__ import annotations

from apps.core.management.commands.repair_member_count import Command as BaseRepairCommand


class Command(BaseRepairCommand):
    help = "按 ACTIVE 成员行重算 Room.member_count（repair_member_count 的别名）。"
