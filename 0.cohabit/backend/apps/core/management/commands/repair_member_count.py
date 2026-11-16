"""``repair_member_count``：修复 ``Room.member_count`` 漂移（docs/06 S-15）。"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.adminops import maintenance


class Command(BaseCommand):
    help = "按 ACTIVE 成员行重算 Room.member_count，检测并修复漂移。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--room",
            type=int,
            default=None,
            help="只处理指定房间 id（默认全量）",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只报告漂移（checked/drift/samples），不写入任何数据",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="dry-run 时最多展示的漂移样例数（默认 20）",
        )

    def handle(self, *args, **options):
        try:
            stats = maintenance.repair_member_counts(
                options["room"],
                dry_run=options["dry_run"],
                limit=options["limit"],
            )
        except ValueError as exc:  # pragma: no cover - 防御性
            raise CommandError(str(exc)) from exc
        self.stdout.write(maintenance.format_stats("repair_member_count", stats))
