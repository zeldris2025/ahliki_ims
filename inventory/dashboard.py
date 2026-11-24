"""Figures for the executive inventory dashboard.

Every number here is read from the database at request time; nothing is estimated or made up.
Stock always comes from the StockMovement ledger. Invoice figures only ever go through
visible_invoices(), so a user never counts invoices of sites they can't see.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Abs, Coalesce, TruncDate, TruncMonth
from django.urls import reverse
from django.utils import timezone

from .models import (SITES, Category, Container, ContainerItem, GoodsReceivedNote, GRNItem, Pallet,
                     PalletLocation, Product, PurchaseOrder, ShelfLocation, StockAlert, StockMovement)
from .navigation import effective_role, view_roles
from .site_access import sees_all_sites, user_sites, visible_invoices

# Which dashboard sections each role sees. Cashiers only get stock levels (they look stock up
# for customers); finance gets value and movement but not floor operations.
SECTION_ROLES = {
    'inventory': ('admin', 'manager', 'finance', 'warehouse', 'cashier'),
    'value': ('admin', 'manager', 'finance', 'warehouse'),
    'movement': ('admin', 'manager', 'finance', 'warehouse'),
    'operations': ('admin', 'manager', 'warehouse'),
    'dispatch': ('admin', 'manager', 'warehouse'),
    'alerts': ('admin', 'manager', 'finance', 'warehouse'),
}

RANGES = {'7': 7, '30': 30, '90': 90, '365': 365}
DEFAULT_RANGE = '30'
EXPIRY_DAYS = 30          # same window the existing expiry alerts use (views.check_and_create_alerts)
TOP_N = 8


def _day(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@dataclass
class Filters:
    range_key: str
    first: date
    last: date
    category: Category | None
    site: str
    site_options: list

    @property
    def days(self):
        return (self.last - self.first).days + 1


def read_filters(request):
    today = timezone.localdate()
    params = request.GET
    range_key = params.get('range', DEFAULT_RANGE)
    first, last = _day(params.get('from', '')), _day(params.get('to', ''))
    if range_key == 'custom' and (first or last):
        last = min(last or today, today)
        first = first or last - timedelta(days=29)
        if first > last:
            first, last = last, first
        first = max(first, last - timedelta(days=730))    # keep the charts readable
    else:
        range_key = range_key if range_key in RANGES else DEFAULT_RANGE
        last, first = today, today - timedelta(days=RANGES[range_key] - 1)

    category = None
    if params.get('category', '').isdigit():
        category = Category.objects.filter(pk=params['category']).first()

    options = list(SITES) if sees_all_sites(request.user) else user_sites(request.user)
    site = params.get('site', '')
    if site not in options:
        site = ''
    return Filters(range_key, first, last, category, site, options)


def _link(user, role, url_name, query=''):
    """URL of a page the user may open, else None (so a KPI is only clickable when it leads somewhere)."""
    allowed = view_roles(url_name)
    if allowed is not None and role not in allowed and not user.is_superuser:
        return None
    return reverse(url_name) + (f'?{query}' if query else '')


def _days(first, last):
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _series(rows, key, days, value='n'):
    found = {r[key]: r[value] or 0 for r in rows}
    return [found.get(d, 0) for d in days]


def _top(rows, label_key, value_key, empty_label):
    """Top N rows plus an 'Other' bucket, so the chart still adds up to the total."""
    rows = [r for r in rows if r[value_key]]
    head, tail = rows[:TOP_N], rows[TOP_N:]
    labels = [r[label_key] or empty_label for r in head]
    values = [float(r[value_key]) for r in head]
    if tail:
        labels.append(f'Other ({len(tail)})')
        values.append(float(sum(r[value_key] for r in tail)))
    return {'labels': labels, 'values': values}


def build(request):
    user = request.user
    role = effective_role(user)
    f = read_filters(request)
    show = {name: role in roles for name, roles in SECTION_ROLES.items()}
    today = timezone.localdate()
    days = _days(f.first, f.last)
    data = {'filters': f, 'show': show, 'today': today, 'role': role}
    link = lambda name, query='': _link(user, role, name, query)  # noqa: E731

    products = Product.objects.filter(is_active=True)
    ledger = StockMovement.objects.filter(product__is_active=True)
    if f.category:
        products = products.filter(category=f.category)
        ledger = ledger.filter(product__category=f.category)
    cat_q = f'category={f.category.pk}' if f.category else ''

    # ── Inventory levels ──────────────────────────────────────────────────────
    stocked = products.annotate(stock=Coalesce(Sum('stock_movements__quantity'), 0))
    total = products.count()
    low = stocked.filter(stock__lte=F('reorder_level')).count()        # existing rule (incl. zero)
    out = stocked.filter(stock__lte=0).count()
    totals = ledger.aggregate(units=Sum('quantity'),
                              value=Sum(F('quantity') * F('product__cost_price'), output_field=DecimalField()))
    expiring_items = GRNItem.objects.filter(product__in=products, expiry_date__gte=today,
                                            expiry_date__lte=today + timedelta(days=EXPIRY_DAYS))
    data['inventory'] = {
        'total': total, 'units': totals['units'] or 0, 'low': low, 'out': out,
        'low_only': low - out, 'healthy': total - low,
        'expiring': expiring_items.values('product').distinct().count(),
        'links': {
            'total': link('product_list', cat_q),
            'low': link('product_list', '&'.join(filter(None, ['stock=low', cat_q]))),
            'out': link('product_list', '&'.join(filter(None, ['stock=out', cat_q]))),
            'expiring': link('alert_list', 'type=expiry&status=open'),
        },
    }

    if show['value']:
        value = totals['value'] or 0
        # Signs that the value isn't trustworthy yet, worked out from the data itself.
        bulk = ledger.filter(reference__startswith='BULK-').aggregate(n=Count('id'), q=Sum('quantity'))
        no_cost = stocked.filter(stock__gt=0, cost_price=0).count()
        by_value = (ledger.values('product').annotate(v=Sum(F('quantity') * F('product__cost_price'),
                                                            output_field=DecimalField()))
                    .order_by('-v')[:10])
        top10 = sum((r['v'] or 0) for r in by_value)
        data['value'] = {
            'total': value, 'no_cost': no_cost,
            'bulk_movements': bulk['n'] or 0, 'bulk_units': bulk['q'] or 0,
            'top10_share': round(float(top10) / float(value) * 100) if value else 0,
            'link': link('reports'),
        }

    # Stock by category / supplier (units and value) — always all categories, for comparison.
    if show['inventory']:
        base = StockMovement.objects.filter(product__is_active=True)
        if f.category:
            by_supplier_base = base.filter(product__category=f.category)
        else:
            by_supplier_base = base
        value_expr = Sum(F('quantity') * F('product__cost_price'), output_field=DecimalField())
        cat_rows = list(base.values(name=F('product__category__name'))
                        .annotate(units=Sum('quantity'), value=value_expr).order_by('-units'))
        sup_rows = list(by_supplier_base.values(name=F('product__supplier__name'))
                        .annotate(units=Sum('quantity'), value=value_expr).order_by('-units'))
        data['by_category'] = _top(cat_rows, 'name', 'units', 'Uncategorised')
        data['by_supplier'] = _top(sup_rows, 'name', 'units', 'No supplier')
        if show['value']:
            data['by_category_value'] = _top(sorted(cat_rows, key=lambda r: r['value'] or 0, reverse=True),
                                             'name', 'value', 'Uncategorised')
            data['by_supplier_value'] = _top(sorted(sup_rows, key=lambda r: r['value'] or 0, reverse=True),
                                             'name', 'value', 'No supplier')
        data['health'] = {'labels': ['Healthy', 'Low', 'Out of stock'],
                          'values': [total - low, low - out, out]}

    # ── Stock movement ───────────────────────────────────────────────────────
    if show['movement']:
        window = ledger.filter(timestamp__date__gte=f.first, timestamp__date__lte=f.last)
        daily = list(window.annotate(d=TruncDate('timestamp')).values('d', 'movement_type')
                     .annotate(q=Sum(Abs('quantity')), n=Count('id')))
        by_type = {}
        for kind, _label in StockMovement.MOVEMENT_TYPES:
            rows = [r for r in daily if r['movement_type'] == kind]
            by_type[kind] = {'units': _series(rows, 'd', days, 'q'), 'count': _series(rows, 'd', days, 'n')}
        type_totals = {r['movement_type']: r for r in
                       window.values('movement_type').annotate(q=Sum(Abs('quantity')), n=Count('id'))}

        year_ago = (today.replace(day=1) - timedelta(days=330)).replace(day=1)
        months = list(ledger.filter(timestamp__date__gte=year_ago).annotate(m=TruncMonth('timestamp'))
                      .values('m').annotate(i=Sum('quantity', filter=Q(quantity__gt=0)),
                                            o=Sum(Abs('quantity'), filter=Q(quantity__lt=0)))
                      .order_by('m'))
        top_out = list(window.filter(quantity__lt=0).values('product__pk', 'product__name', 'product__unit')
                       .annotate(q=Sum(Abs('quantity')), n=Count('id')).order_by('-q')[:10])
        data['movement'] = {
            'labels': [d.strftime('%d %b') for d in days],
            'series': by_type,
            'totals': {kind: type_totals.get(kind, {'q': 0, 'n': 0}) for kind, _ in StockMovement.MOVEMENT_TYPES},
            'months': {'labels': [_month_label(r['m']) for r in months],
                       'in': [r['i'] or 0 for r in months], 'out': [r['o'] or 0 for r in months]},
            'top_out': top_out,
            'link': link('stock_movements'),
        }

    # ── Warehouse operations ─────────────────────────────────────────────────
    if show['operations']:
        status_counts = dict(Container.objects.values_list('status').annotate(n=Count('id')))
        statuses = [(key, label, status_counts.get(key, 0)) for key, label in Container.STATUS_CHOICES]
        opened = ContainerItem.objects.filter(container__status=Container.STATUS_OPENED)
        manifest = opened.aggregate(t=Sum('quantity'))['t'] or 0
        palletized = (Pallet.objects.filter(container_item__container__status=Container.STATUS_OPENED)
                      .aggregate(t=Sum('quantity'))['t'] or 0)
        current = PalletLocation.objects.filter(is_current=True)
        pallets = Pallet.objects.count()
        shelved = current.values('pallet').distinct().count()
        shelves = ShelfLocation.objects.count()
        occupied = current.values('shelf').distinct().count()
        data['operations'] = {
            'statuses': statuses,
            'active': sum(n for key, _, n in statuses if key != Container.STATUS_CLOSED),
            'awaiting_receipt': status_counts.get(Container.STATUS_AT_WHARF, 0) + status_counts.get(Container.STATUS_CHECKED_IN, 0),
            'unloading': status_counts.get(Container.STATUS_OPENED, 0),
            'manifest_units': manifest, 'palletized_units': min(palletized, manifest) if manifest else palletized,
            'palletized_pct': round(min(palletized, manifest) / manifest * 100) if manifest else None,
            'pallets': pallets, 'shelved': shelved, 'unshelved': max(pallets - shelved, 0),
            'shelves': shelves, 'occupied': occupied, 'available': max(shelves - occupied, 0),
            'open_pos': PurchaseOrder.objects.filter(status__in=('pending', 'partial')).count(),
            'grns': GoodsReceivedNote.objects.filter(received_at__date__gte=f.first, received_at__date__lte=f.last).count(),
            'links': {
                'containers': link('warehouse_container_list'),
                'pallets': link('pallet_list'),
                'unshelved': link('pallet_list', 'location=unshelved'),
                'shelves': link('shelf_list'),
                'grns': link('grn_list'),
            },
        }

    # ── Alerts ───────────────────────────────────────────────────────────────
    if show['alerts']:
        open_alerts = StockAlert.objects.filter(is_resolved=False)
        open_by_type = dict(open_alerts.values_list('alert_type').annotate(n=Count('id')))
        data['alerts'] = {
            'open': sum(open_by_type.values()),
            'by_type': [(key, label, open_by_type.get(key, 0)) for key, label in StockAlert.ALERT_TYPES],
            'new': StockAlert.objects.filter(created_at__date__gte=f.first, created_at__date__lte=f.last).count(),
            'resolved': StockAlert.objects.filter(resolved_at__date__gte=f.first, resolved_at__date__lte=f.last).count(),
            'discrepancy_grns': GoodsReceivedNote.objects.filter(has_discrepancy=True, received_at__date__gte=f.first,
                                                                 received_at__date__lte=f.last).count(),
            'latest': open_alerts.select_related('product').order_by('-created_at')[:6],
            'link': link('alert_list', 'status=open'),
        }

    # ── Dispatch (site-checked) ──────────────────────────────────────────────
    if show['dispatch']:
        invoices = visible_invoices(user)
        if f.site:
            invoices = invoices.filter(site=f.site)
        pending = invoices.filter(dispatch_status='pending')
        dispatched = invoices.filter(dispatch_status='dispatched', dispatched_at__date__gte=f.first,
                                     dispatched_at__date__lte=f.last)
        daily = list(dispatched.annotate(d=TruncDate('dispatched_at')).values('d').annotate(n=Count('id')))
        pending_sites = dict(pending.values_list('site').annotate(n=Count('id')))
        done_sites = dict(dispatched.values_list('site').annotate(n=Count('id')))
        sites = [s for s in f.site_options if not f.site or s == f.site]
        site_q = f'site={f.site}' if f.site else ''
        data['dispatch'] = {
            'pending': pending.count(),
            'pending_today': pending.filter(created_at__date=today).count(),
            'picking': pending.filter(items__isnull=False).distinct().count(),
            'dispatched': dispatched.count(),
            'dispatched_today': invoices.filter(dispatch_status='dispatched', dispatched_at__date=today).count(),
            'daily': _series(daily, 'd', days),
            'sites': {'labels': sites, 'pending': [pending_sites.get(s, 0) for s in sites],
                      'dispatched': [done_sites.get(s, 0) for s in sites]},
            'recent': pending.select_related('ls_central').order_by('-created_at')[:8],
            'links': {
                'pending': link('warehouse_dispatch_list', '&'.join(filter(None, ['when=all', site_q]))),
                'today': link('warehouse_dispatch_list', site_q),
                'log': link('warehouse_dispatch_list', '&'.join(filter(None, ['tab=log', site_q]))),
            },
        }

    data['kpis'] = _kpis(data, show)
    data['categories'] = Category.objects.order_by('name')
    data['recent_grns'] = (GoodsReceivedNote.objects.select_related('supplier').order_by('-received_at')[:5]
                           if show['operations'] else ())
    return data


def _month_label(value):
    # TruncMonth already works in the current (Apia) time zone.
    return value.strftime('%b %Y') if value else ''


def _short(value):
    """1234567 -> '1.2M' for figures too wide for a card (the exact value goes in its tooltip)."""
    for size, suffix in ((1_000_000_000, 'B'), (1_000_000, 'M')):
        if abs(value) >= size:
            return f'{value / size:,.1f}{suffix}'
    return None


def _kpi(label, value, icon, href=None, sub='', tone='', decimals=0, prefix='', flag=False):
    short = _short(float(value or 0)) if prefix else None
    return {'label': label, 'value': value, 'icon': icon, 'href': href, 'sub': sub, 'tone': tone,
            'decimals': decimals, 'prefix': prefix, 'flag': flag, 'short': short}


def _kpis(data, show):
    """The headline cards, in reading order, for the sections this role sees."""
    inv = data['inventory']
    cards = [
        _kpi('Total products', inv['total'], 'package', inv['links']['total'], 'Active SKUs'),
        _kpi('Stock units', inv['units'], 'layers', inv['links']['total'], 'On hand, from the stock ledger'),
    ]
    if show['value']:
        v = data['value']
        cards.append(_kpi('Stock value', v['total'], 'coins', v['link'], 'Units × cost price', 'money',
                          prefix='SAT$', flag=bool(v['bulk_movements'] or v['top10_share'] >= 50)))
    cards += [
        _kpi('Low stock', inv['low_only'], 'alert', inv['links']['low'], 'At or below reorder level', 'warning'),
        _kpi('Out of stock', inv['out'], 'x', inv['links']['out'], 'Nothing on hand', 'danger'),
        _kpi('Expiring soon', inv['expiring'], 'clock', inv['links']['expiring'],
             f'Products with a batch expiring within {EXPIRY_DAYS} days', 'warning'),
    ]
    if show['operations']:
        o = data['operations']
        cards.append(_kpi('Awaiting receipt', o['awaiting_receipt'], 'inbox', o['links']['containers'],
                          'Containers at wharf or checked in'))
    if show['dispatch']:
        d = data['dispatch']
        cards.append(_kpi('Pending dispatch', d['pending'], 'truck', d['links']['pending'],
                          f"{d['pending_today']:,} arrived today", 'primary'))
    if show['operations']:
        o = data['operations']
        cards += [
            _kpi('Active containers', o['active'], 'container', o['links']['containers'], 'Not yet closed'),
            _kpi('Pallets', o['pallets'], 'layers', o['links']['unshelved'] or o['links']['pallets'],
                 f"{o['unshelved']:,} awaiting shelving"),
            _kpi('Available shelves', o['available'], 'shelves', o['links']['shelves'],
                 f"{o['occupied']:,} of {o['shelves']:,} in use"),
        ]
    return cards
