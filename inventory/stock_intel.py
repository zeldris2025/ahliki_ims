"""Stock status rules and the Stock Intelligence workspace figures.

Stock on hand always comes from the StockMovement ledger (sum of quantities); nothing here
stores or edits a stock figure. The status rules are the ones the app already used:

* out      stock is zero or below
* low      stock is at or below the product's reorder level (``Product.is_low_stock``)
* healthy  stock is above the reorder level
* expiring a received batch (GRNItem) expires within EXPIRY_DAYS, the same window the
           existing expiry alerts and the counter stock lookup use.
"""
from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Abs, Coalesce, TruncDate, TruncMonth
from django.utils import timezone

from .models import GoodsReceivedNote, GRNItem, Product, StockAlert, StockMovement

EXPIRY_DAYS = 30
RANK_N = 10

STATUS_LABELS = {'healthy': 'Healthy', 'low': 'Low', 'out': 'Out of stock'}


def stock_status(stock, reorder_level):
    if stock <= 0:
        return 'out'
    if stock <= reorder_level:
        return 'low'
    return 'healthy'


def with_stock(products):
    return products.annotate(stock=Coalesce(Sum('stock_movements__quantity'), 0))


def expiry_window(today=None):
    today = today or timezone.localdate()
    return today, today + timedelta(days=EXPIRY_DAYS)


def expiring_product_ids(product_ids=None):
    """Products with a received batch expiring in the next EXPIRY_DAYS (not already expired)."""
    today, soon = expiry_window()
    items = GRNItem.objects.filter(expiry_date__gte=today, expiry_date__lte=soon)
    if product_ids is not None:
        items = items.filter(product_id__in=product_ids)
    return set(items.values_list('product_id', flat=True))


def batch_status(expiry_date, today=None):
    if not expiry_date:
        return 'none'
    today, soon = expiry_window(today)
    if expiry_date < today:
        return 'expired'
    if expiry_date <= soon:
        return 'expiring'
    return 'ok'


def balance_series(product, days):
    """Stock on hand at the end of each day in ``days`` (a list of dates), from the ledger."""
    first = days[0]
    moves = product.stock_movements
    opening = moves.filter(timestamp__date__lt=first).aggregate(t=Sum('quantity'))['t'] or 0
    daily = dict(moves.filter(timestamp__date__gte=first, timestamp__date__lte=days[-1])
                 .annotate(d=TruncDate('timestamp')).values_list('d').annotate(q=Sum('quantity')))
    out, running = [], opening
    for d in days:
        running += daily.get(d, 0) or 0
        out.append(running)
    return out


def _days(first, last):
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _series(rows, days, key='q'):
    found = {r['d']: r[key] or 0 for r in rows}
    return [found.get(d, 0) for d in days]


def _ranking(window, condition):
    return list(window.filter(condition).values('product__pk', 'product__sku', 'product__name', 'product__unit')
                .annotate(q=Sum(Abs('quantity')), n=Count('id')).order_by('-q', 'product__name')[:RANK_N])


def build(filters):
    """Figures for the Stock Intelligence page. ``filters`` is a dashboard.Filters."""
    f = filters
    today = timezone.localdate()
    days = _days(f.first, f.last)

    products = Product.objects.filter(is_active=True)
    ledger = StockMovement.objects.filter(product__is_active=True)
    if f.category:
        products = products.filter(category=f.category)
        ledger = ledger.filter(product__category=f.category)

    stocked = with_stock(products)
    total = products.count()
    low = stocked.filter(stock__lte=F('reorder_level')).count()
    out = stocked.filter(stock__lte=0).count()
    _, soon = expiry_window(today)
    batches = GRNItem.objects.filter(product__in=products, expiry_date__isnull=False)
    open_alerts = StockAlert.objects.filter(is_resolved=False, product__in=products)

    health = {
        'total': total,
        'healthy': total - low,
        'low': low - out,
        'out': out,
        'expiring': batches.filter(expiry_date__gte=today, expiry_date__lte=soon).values('product').distinct().count(),
        'expired_batches': batches.filter(expiry_date__lt=today).count(),
        'discrepancy_alerts': open_alerts.filter(alert_type='discrepancy').count(),
        'discrepancy_grns': GoodsReceivedNote.objects.filter(
            has_discrepancy=True, received_at__date__gte=f.first, received_at__date__lte=f.last).count(),
        'open_alerts': open_alerts.count(),
    }

    window = ledger.filter(timestamp__date__gte=f.first, timestamp__date__lte=f.last)
    by_day_type = list(window.annotate(d=TruncDate('timestamp')).values('d', 'movement_type')
                       .annotate(q=Sum(Abs('quantity')), n=Count('id')))

    def kind(name, key='q'):
        return _series([r for r in by_day_type if r['movement_type'] == name], days, key)

    adj_daily = list(window.filter(movement_type='adjustment').annotate(d=TruncDate('timestamp')).values('d')
                     .annotate(up=Sum('quantity', filter=Q(quantity__gt=0)),
                               down=Sum(Abs('quantity'), filter=Q(quantity__lt=0))))
    totals = {r['movement_type']: r for r in
              window.values('movement_type').annotate(q=Sum(Abs('quantity')), n=Count('id'))}
    net = window.aggregate(t=Sum('quantity'))['t'] or 0

    year_ago = (today.replace(day=1) - timedelta(days=330)).replace(day=1)
    months = list(ledger.filter(timestamp__date__gte=year_ago).annotate(m=TruncMonth('timestamp'))
                  .values('m').annotate(i=Sum('quantity', filter=Q(quantity__gt=0)),
                                        o=Sum(Abs('quantity'), filter=Q(quantity__lt=0)),
                                        a=Count('id', filter=Q(movement_type='adjustment')))
                  .order_by('m'))

    labels = [d.strftime('%d %b') for d in days]
    charts = {
        'inout': {'type': 'bar', 'labels': labels, 'datasets': [
            {'label': 'Stock in', 'data': kind('in')},
            {'label': 'Stock out', 'data': kind('out')},
        ]},
        'daily': {'type': 'bar', 'stacked': True, 'labels': labels, 'datasets': [
            {'label': label, 'data': kind(key)} for key, label in
            (('in', 'Received'), ('out', 'Dispatched / out'), ('adjustment', 'Adjustments'), ('return', 'Returns'))
        ]},
        'months': {'type': 'bar', 'labels': [m['m'].strftime('%b %Y') for m in months if m['m']], 'datasets': [
            {'label': 'Units in', 'data': [m['i'] or 0 for m in months if m['m']]},
            {'label': 'Units out', 'data': [m['o'] or 0 for m in months if m['m']]},
        ]},
        'adjust': {'type': 'bar', 'labels': labels, 'datasets': [
            {'label': 'Adjusted up', 'data': _series(adj_daily, days, 'up')},
            {'label': 'Adjusted down', 'data': _series(adj_daily, days, 'down')},
        ]},
    }

    return {
        'health': health,
        'totals': {k: totals.get(k, {'q': 0, 'n': 0}) for k, _ in StockMovement.MOVEMENT_TYPES},
        'net': net,
        'entries': sum(t['n'] for t in totals.values()),
        'rank_out': _ranking(window, Q(quantity__lt=0)),
        'rank_in': _ranking(window, Q(quantity__gt=0)),
        'rank_adjust': list(window.filter(movement_type='adjustment')
                            .values('product__pk', 'product__sku', 'product__name', 'product__unit')
                            .annotate(n=Count('id'), q=Sum('quantity')).order_by('-n', 'product__name')[:RANK_N]),
        'recent_adjustments': (window.filter(movement_type='adjustment')
                               .select_related('product', 'performed_by').order_by('-timestamp')[:12]),
        'charts': charts,
        'bulk': ledger.filter(reference__startswith='BULK-').aggregate(n=Count('id'), q=Sum('quantity')),
    }
