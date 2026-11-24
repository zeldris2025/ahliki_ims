from django.core.management.base import BaseCommand, CommandError

from ls_central.sync import sync_invoices


class Command(BaseCommand):
    help = 'Import new LS Central sales invoices into Warehouse Dispatch.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, help='How many days back to look (default LS_CENTRAL_SYNC_DAYS).')

    def handle(self, *args, days=None, **options):
        run = sync_invoices(days=days)
        if run is None:
            raise CommandError('Another LS Central sync is running. Try again when it has finished.')
        if not run.ok:
            raise CommandError(run.message)
        self.stdout.write(self.style.SUCCESS(run.message))
