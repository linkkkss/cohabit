"""``expire_connections``：关闭到期的在途组寝请求（docs/02 §3.6）。"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.adminops import maintenance


class Command(BaseCommand):
    help = "关闭到期的在途组寝请求（EXPIRED/TIMEOUT），cron 每 10 分钟。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计到期的请求，不写入任何数据",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=maintenance.BATCH_LIMIT,
            help=f"单次最多处理的请求数（默认 {maintenance.BATCH_LIMIT}）",
        )

    def handle(self, *args, **options):
        stats = maintenance.expire_connections(
            limit=options["limit"],
            dry_run=options["dry_run"],
        )
        self.stdout.write(maintenance.format_stats("expire_connections", stats))
