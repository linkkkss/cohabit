"""``send_window_reminders``：结束前 7/3/1 天发送 WINDOW_CLOSING（docs/02 §7.5）。"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.adminops import maintenance


class Command(BaseCommand):
    help = "组寝窗口关闭提醒：结束前 7/3/1 天各发一次 WINDOW_CLOSING（每日 cron）。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计应发送的提醒，不写入通知",
        )

    def handle(self, *args, **options):
        stats = maintenance.send_window_reminders(dry_run=options["dry_run"])
        self.stdout.write(maintenance.format_stats("send_window_reminders", stats))
