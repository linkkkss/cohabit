"""``archive_rooms``：窗口结束归档（docs/02 §7.4）。"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.adminops import maintenance


class Command(BaseCommand):
    help = "窗口结束：先过期在途请求，再归档寝室（ARCHIVED），cron 每 10 分钟。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计待过期的请求与待归档的寝室，不写入任何数据",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=maintenance.BATCH_LIMIT,
            help=f"单次最多归档的房间数（默认 {maintenance.BATCH_LIMIT}）",
        )

    def handle(self, *args, **options):
        stats = maintenance.archive_rooms(
            limit=options["limit"],
            dry_run=options["dry_run"],
        )
        self.stdout.write(maintenance.format_stats("archive_rooms", stats))
