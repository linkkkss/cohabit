"""``expire_transfers``：关闭超时未处理的寝室转让（docs/02 §6）。"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.adminops import maintenance


class Command(BaseCommand):
    help = "超过 24h 未处理的 PENDING 转让置 EXPIRED 并通知双方。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计到期的转让，不写入任何数据",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=maintenance.BATCH_LIMIT,
            help=f"单次最多处理的转让数（默认 {maintenance.BATCH_LIMIT}）",
        )

    def handle(self, *args, **options):
        stats = maintenance.expire_transfers(
            limit=options["limit"],
            dry_run=options["dry_run"],
        )
        self.stdout.write(maintenance.format_stats("expire_transfers", stats))
