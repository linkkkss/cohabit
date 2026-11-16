"""``cleanup_notifications``：清理过期站内信（docs/02 §8.1）。"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.adminops import maintenance


class Command(BaseCommand):
    help = "清理已读 90 天 / 未读 180 天的站内信，审计不受影响（每日 cron）。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计待清理的通知，不删除任何数据",
        )

    def handle(self, *args, **options):
        stats = maintenance.cleanup_notifications(dry_run=options["dry_run"])
        self.stdout.write(maintenance.format_stats("cleanup_notifications", stats))
