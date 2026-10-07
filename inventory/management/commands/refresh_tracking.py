from django.conf import settings
from django.core.management.base import BaseCommand

from inventory.terminal49 import refresh_stale


class Command(BaseCommand):
    help = 'Re-sync tracked B/Ls still on the water with Terminal49 (those not synced within --hours).'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=float,
                            default=getattr(settings, 'TRACKING_AUTO_REFRESH_HOURS', 4) or 4,
                            help='Only refresh shipments last synced longer ago than this (0 = all).')

    def handle(self, *args, **options):
        synced, failed = refresh_stale(options['hours'])
        self.stdout.write(self.style.SUCCESS(f'Refreshed {synced} tracked shipment(s); {failed} failed.'))
