"""Daily container report email: CMS yard boxes (return deadlines, yesterday's moves) and the
warehouse containers still being unloaded. Sent by inventory/scheduler.py each morning, or by hand
with `manage.py send_container_report`."""
import csv
import io
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Sum
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import (CmsContainer, Container, ContainerComment, ContainerReturn, ContainerTransfer,
                     Pallet, Yard)

DUE_SOON_DAYS = 7
MAX_ROWS = 40   # per table; the attached CSV has every container


def build_context():
    now = timezone.localtime()
    today = now.date()
    since = now - timedelta(hours=24)

    active = list(CmsContainer.objects.filter(returned=False).select_related('yard', 'owner')
                  .order_by('arrival_date', 'code'))
    overdue = sorted((c for c in active if c.is_overdue), key=lambda c: (c.days_left, c.code))
    due_soon = sorted((c for c in active if c.days_left is not None and 0 <= c.days_left <= DUE_SOON_DAYS),
                      key=lambda c: (c.days_left, c.code))
    status_counts = Counter(c.status for c in active)

    per_yard = {}
    for c in active:
        row = per_yard.setdefault(c.yard.code, {'yard': c.yard.code, 'full': 0, 'storage': 0, 'empty': 0,
                                                'overdue': 0, 'total': 0})
        row[c.status] += 1
        row['total'] += 1
        row['overdue'] += c.is_overdue
    yards = sorted(per_yard.values(), key=lambda r: (-r['total'], r['yard']))

    warehouse = list(Container.objects.exclude(status=Container.STATUS_CLOSED)
                     .select_related('supplier', 'container_type')
                     .annotate(qty=Sum('items__quantity')).order_by('arrival_date', 'container_number'))
    palletized = dict(Pallet.objects.filter(container_item__container__in=[c.pk for c in warehouse])
                      .values_list('container_item__container').annotate(t=Sum('quantity')))
    for c in warehouse:
        c.qty = c.qty or 0
        c.done = palletized.get(c.pk, 0)
        c.percent = round(100 * c.done / c.qty) if c.qty else 0
        c.days_waiting = (today - c.arrival_date).days if c.arrival_date else None

    # What happened in the last 24 hours.
    warehouse_moves = []
    for field, label in (('created_at', 'Lodged'), ('checked_in_at', 'Checked in at HQ'),
                         ('opened_at', 'Opened'), ('palletized_at', 'Palletized'), ('closed_at', 'Closed')):
        for c in Container.objects.filter(**{f'{field}__gte': since}):
            warehouse_moves.append({'when': timezone.localtime(getattr(c, field)),
                                    'container': c.container_number, 'what': label})
    warehouse_moves.sort(key=lambda m: m['when'])

    activity = {
        'added': list(CmsContainer.objects.filter(created_at__gte=since).select_related('yard', 'owner')),
        'returned': list(ContainerReturn.objects.filter(created_at__gte=since).select_related('container', 'yard')),
        'transfers': list(ContainerTransfer.objects.filter(created_at__gte=since)
                          .select_related('container', 'from_yard', 'to_yard')),
        'warehouse': warehouse_moves,
        'damage': list(ContainerComment.objects.filter(created_at__gte=since, is_damage=True)
                       .select_related('container', 'author')),
    }
    activity['any'] = any(activity.values())

    site = settings.SITE_URL
    return {
        'today': today,
        'now': now,
        'since': since,
        'site_url': site,
        'links': {
            'cms': site + reverse('cms_dashboard') if site else '',
            'overdue': site + reverse('cms_containers') + '?due=overdue' if site else '',
            'warehouse': site + reverse('warehouse_container_list') if site else '',
        },
        'stats': {
            'active': len(active),
            'wharf': sum(c.yard.code == Yard.WHARF for c in active),
            'full': status_counts[CmsContainer.STATUS_FULL],
            'storage': status_counts[CmsContainer.STATUS_STORAGE],
            'empty': status_counts[CmsContainer.STATUS_EMPTY],
            'overdue': len(overdue),
            'due_soon': len(due_soon),
            'warehouse_open': len(warehouse),
        },
        'overdue': overdue,
        'due_soon': due_soon,
        'due_soon_days': DUE_SOON_DAYS,
        'max_rows': MAX_ROWS,
        'overdue_more': max(len(overdue) - MAX_ROWS, 0),
        'due_soon_more': max(len(due_soon) - MAX_ROWS, 0),
        'yards': yards,
        'warehouse': warehouse,
        'activity': activity,
        'active': active,
    }


def active_csv(active):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Container', 'Description', 'Yard', 'Status', 'Owner', 'Vessel voyage', 'Arrival date',
                'Return due', 'Days left', 'Days on island', 'Driver', 'Note'])
    for c in active:
        w.writerow([c.code, c.description, c.yard.code, c.get_status_display(), c.owner.name, c.vessel_voyage,
                    c.arrival_date or '', c.return_due or '', '' if c.days_left is None else c.days_left,
                    '' if c.days_on_island is None else c.days_on_island, c.driver, c.note.replace('\n', ' / ')])
    return out.getvalue().encode('utf-8-sig')   # BOM so Excel reads it as UTF-8


def build_message(recipients):
    ctx = build_context()
    s = ctx['stats']
    subject = f"Container report {ctx['today']:%a %d %b %Y}: {s['active']} in yards"
    if s['overdue']:
        subject += f", {s['overdue']} overdue"
    msg = EmailMultiAlternatives(subject, render_to_string('emails/container_report.txt', ctx),
                                 to=recipients)
    msg.attach_alternative(render_to_string('emails/container_report.html', ctx), 'text/html')
    msg.attach(f"containers-{ctx['today']:%Y-%m-%d}.csv", active_csv(ctx['active']), 'text/csv')
    return msg


def send_report(recipients=None):
    """Send today's report. Returns a short result line for the log / ScheduledRun."""
    recipients = recipients or settings.CONTAINER_REPORT_RECIPIENTS
    if not recipients:
        return 'Skipped: CONTAINER_REPORT_RECIPIENTS is empty'
    build_message(recipients).send()
    return f'Sent to {", ".join(recipients)}'
