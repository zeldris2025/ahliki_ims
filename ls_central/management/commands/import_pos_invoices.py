from collections import Counter
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ls_central.client import LsCentralClient, LsCentralError
from ls_central.pos import MAX_DAYS, not_yet_imported, pos_invoices, save_invoices, store_of
from ls_central.sync import ProductMatcher


class Command(BaseCommand):
    help = (f'Get POS invoices of the past {MAX_DAYS} days (and today) from the LS Central ledgers. '
            'Only previews unless --save is given; with --save they are added to Pending Dispatch.')

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='start', type=date.fromisoformat,
                            help=f'First posting date, YYYY-MM-DD. At most, and by default, {MAX_DAYS} days ago.')
        parser.add_argument('--to', dest='end', type=date.fromisoformat,
                            help='Last posting date, YYYY-MM-DD (default today).')
        parser.add_argument('--store', nargs='+', help='Only these stores, e.g. --store HDQ SAV.')
        parser.add_argument('--save', action='store_true', help='Write them into the database.')

    def handle(self, *args, start=None, end=None, store=None, save=False, **options):
        today = timezone.localdate()
        earliest = today - timedelta(days=MAX_DAYS)
        start = start or earliest
        end = min(end or today, today)      # LS Central has some entries dated years ahead
        if start < earliest:
            raise CommandError(f'Only the past {MAX_DAYS} days can be imported: '
                               f'--from can be {earliest.isoformat()} at the earliest.')
        if start > end:
            raise CommandError('--from is after --to.')
        found = new = added = 0
        day = start
        try:
            client = LsCentralClient.from_settings()
            matcher = ProductMatcher()
            while day <= end:
                docs = pos_invoices(client, day, store)
                fresh = not_yet_imported(docs)
                found += len(docs)
                new += len(fresh)
                by_store = ', '.join(f'{s} {n}' for s, n in
                                     sorted(Counter(store_of(d['number']) for d in docs).items()))
                self.stdout.write(f'{day:%a %d %b %Y}: {len(docs)} invoices, {len(fresh)} new'
                                  + (f' ({by_store})' if by_store else ''))
                self.stdout.flush()
                if save:
                    added += save_invoices(fresh, matcher)
                day += timedelta(days=1)
        except LsCentralError as exc:
            raise CommandError(f'Stopped at {day}: {exc} Run it again to carry on; '
                               'invoices already imported are skipped.') from None

        if save:
            self.stdout.write(self.style.SUCCESS(
                f'{added} invoices added to Pending Dispatch, {len(matcher.created)} products added to the catalogue.'))
        else:
            self.stdout.write(f'Preview only, nothing was saved: {found} invoices, {new} not imported yet. '
                              'Add --save to import them.')
