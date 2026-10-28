from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from inventory.container_report import build_message, send_report
from inventory.scheduler import run_once_today


class Command(BaseCommand):
    help = ('Email the daily container report now. The app already sends it every day at '
            'CONTAINER_REPORT_TIME; use this to test, or from an external scheduler with --once-a-day.')

    def add_arguments(self, parser):
        parser.add_argument('--to', nargs='+', help='Send to these addresses instead of CONTAINER_REPORT_RECIPIENTS.')
        parser.add_argument('--preview', metavar='FILE', help='Write the email as an HTML file instead of sending it.')
        parser.add_argument('--once-a-day', action='store_true',
                            help="Skip if today's report has already gone out (for cron / Azure schedulers).")

    def handle(self, *args, **options):
        if options['preview']:
            msg = build_message(options['to'] or settings.CONTAINER_REPORT_RECIPIENTS or ['preview@example.com'])
            Path(options['preview']).write_text(msg.alternatives[0][0], encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'Subject: {msg.subject}\nWritten to {options["preview"]}'))
            return
        if options['once_a_day']:
            result = run_once_today('container_report', lambda: send_report(options['to']))
            result = result or "Skipped: today's report was already sent."
        else:
            result = send_report(options['to'])
        self.stdout.write(self.style.SUCCESS(result))
