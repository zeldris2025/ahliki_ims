import csv
import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, Count, Min, Q, F, Case, When, Value, IntegerField, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce, Greatest
from django.template.defaultfilters import pluralize
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from .models import (Product, Category, Supplier, GoodsReceivedNote, GRNItem,
                     StockMovement, Sale, SaleItem, StockAlert, PurchaseOrder, UserProfile,
                     Pallet, ShelfLocation, PalletLocation, DispatchComment,
                     Container, ContainerItem, ContainerComment, ShipmentTracking,
                     CmsContainer, ShippingLine, Yard)
from .forms import (ProductForm, SupplierForm, CategoryForm, GRNForm, GRNItemFormSet,
                    SaleForm, SaleItemFormSet, StockAdjustForm,
                    PalletForm, CheckInForm, TransferForm, PalletEditForm,
                    ContainerForm, ContainerItemFormSet, ContainerCommentForm,
                    ContainerPalletForm, ShipmentTrackingForm, ShelfAddForm, ShelfEditForm)
from . import auto_refresh, cms_audit, stock_intel, terminal49


from .models import SITES
from django.http import Http404
from django.views.static import serve

from .site_access import get_visible_invoice, mask_other_sites, sees_all_sites, user_sites, visible_invoices


def role_required(*roles):
    from functools import wraps
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            # Superusers always have access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            if profile.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "You don't have permission to access that page.")
            if profile.role == 'wms_operator':
                return redirect('wms_checkin')
            if profile.role == 'wms_dispatcher':
                return redirect('wms_dispatcher_dashboard')
            if profile.role == 'custom_broker':
                return redirect('cms_dashboard')
            if profile.role == 'cashier':
                return redirect('invoice_upload')
            return redirect('invoice_upload')
        # Read by the sidebar (inventory/navigation.py) so a menu link is only shown to roles
        # this view will actually let in.
        _wrapped.allowed_roles = frozenset(roles)
        return _wrapped
    return decorator


def with_stock(products):
    """Annotate ``stock`` in SQL — reading ``Product.current_stock`` in a loop is one query per product."""
    return products.annotate(stock=Coalesce(Sum('stock_movements__quantity'), 0))


def stock_by_product(product_ids):
    """{product_id: stock} for a handful of products, in one query."""
    rows = (StockMovement.objects.filter(product_id__in=product_ids)
            .values('product_id').annotate(total=Sum('quantity')))
    stock = dict.fromkeys(product_ids, 0)
    stock.update({r['product_id']: r['total'] or 0 for r in rows})
    return stock


def total_stock_value():
    """Sum of stock × cost price over active products, in one query."""
    return StockMovement.objects.filter(product__is_active=True).aggregate(
        t=Sum(F('quantity') * F('product__cost_price'), output_field=DecimalField()))['t'] or 0


def check_and_create_alerts(product):
    """Create stock alerts for a product if needed."""
    # Low stock alert
    if product.is_low_stock:
        StockAlert.objects.get_or_create(
            product=product,
            alert_type='low_stock',
            is_resolved=False,
            defaults={'message': f"{product.name} is below reorder level. Current stock: {product.current_stock}, Reorder level: {product.reorder_level}"}
        )
    # Expiry alert — check GRN items expiring within 30 days
    soon = timezone.localdate() + timedelta(days=30)
    expiring = GRNItem.objects.filter(product=product, expiry_date__lte=soon, expiry_date__gte=timezone.localdate())
    for item in expiring:
        StockAlert.objects.get_or_create(
            product=product,
            alert_type='expiry',
            is_resolved=False,
            defaults={'message': f"Batch {item.batch_number or 'N/A'} of {product.name} expires on {item.expiry_date}."}
        )


@login_required
@role_required('admin', 'manager', 'finance', 'warehouse', 'cashier')
def dashboard(request):
    """Executive inventory dashboard. The figures come from inventory/dashboard.py."""
    from . import dashboard as figures
    data = figures.build(request)
    f = data['filters']
    products = with_stock(Product.objects.filter(is_active=True))
    if f.category:
        products = products.filter(category=f.category)
    low_stock = products.filter(stock__lte=F('reorder_level'), stock__gt=0).order_by('stock', 'name')
    out_of_stock = products.filter(stock__lte=0).order_by('name')
    # Keep the filters on paging links; each table pages on its own.
    keep = request.GET.copy()
    for k in ('low_page', 'out_page'):
        keep.pop(k, None)
    data.update({
        'low_stock_page': Paginator(low_stock, 10).get_page(request.GET.get('low_page')),
        'out_of_stock_page': Paginator(out_of_stock, 10).get_page(request.GET.get('out_page')),
        'keep_query': keep.urlencode(),
        'range_choices': [('7', '7 days'), ('30', '30 days'), ('90', '90 days'), ('365', '12 months')],
        'chart_data': _dashboard_charts(data),
    })
    return render(request, 'dashboard.html', data)


def _dashboard_charts(data):
    """Only the series the charts need, for the page's JSON block."""
    out = {}
    for key in ('by_category', 'by_supplier', 'by_category_value', 'by_supplier_value', 'health'):
        if key in data:
            out[key] = data[key]
    if 'movement' in data:
        m = data['movement']
        out['movement'] = {'labels': m['labels'], 'series': m['series'], 'months': m['months']}
    if 'dispatch' in data:
        d = data['dispatch']
        out['dispatch'] = {'labels': data['movement']['labels'] if 'movement' in data else
                           [day.strftime('%d %b') for day in _date_span(data['filters'])],
                           'daily': d['daily'], 'sites': d['sites']}
    if 'operations' in data:
        out['containers'] = {'labels': [label for _, label, _ in data['operations']['statuses']],
                             'values': [n for _, _, n in data['operations']['statuses']]}
    return out


def _date_span(f):
    return [f.first + timedelta(days=i) for i in range(f.days)]


# ── PRODUCTS ──────────────────────────────────────────────────────────────────

PRODUCTS_PER_PAGE = 50

# Sortable product columns: ?sort=<key> or ?sort=-<key>.
PRODUCT_SORTS = {
    'sku': ('sku',), 'name': ('name',), 'category': ('category__name', 'name'),
    'supplier': ('supplier__name', 'name'), 'stock': ('stock', 'name'), 'price': ('unit_price', 'name'),
    'cost': ('cost_price', 'name'), 'reorder': ('reorder_level', 'name'),
}
# Cost prices are for the stock and finance side, not the sales counter.
COST_ROLES = ('admin', 'manager', 'finance', 'warehouse')


def _role(user):
    from .navigation import effective_role
    return effective_role(user)


def _may_open(user, url_name):
    """True if the user's role passes that view's role_required (menus and buttons use it)."""
    from .navigation import effective_role, view_roles
    allowed = view_roles(url_name)
    return user.is_superuser or allowed is None or effective_role(user) in allowed


@login_required
def product_list(request):
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    supplier_id = request.GET.get('supplier', '')
    stock_status = request.GET.get('stock', '')
    active = request.GET.get('active', '')
    sort = request.GET.get('sort', 'name')
    products = Product.objects.select_related('category', 'supplier')
    if active == 'inactive':
        products = products.filter(is_active=False)
    elif active != 'all':
        active = ''
        products = products.filter(is_active=True)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
    if category_id:
        products = products.filter(category_id=category_id)
    if supplier_id:
        products = products.filter(supplier_id=supplier_id)
    products = with_stock(products)
    # Same rules as the dashboard: low = at or below reorder level but above zero; out = zero or less.
    stock_filters = {'low': Q(stock__lte=F('reorder_level'), stock__gt=0), 'out': Q(stock__lte=0),
                     'healthy': Q(stock__gt=F('reorder_level')),
                     'expiring': Q(pk__in=stock_intel.expiring_product_ids())}
    if stock_status in stock_filters:
        products = products.filter(stock_filters[stock_status])
    else:
        stock_status = ''
    sort_key = sort.lstrip('-')
    if sort_key not in PRODUCT_SORTS:
        sort, sort_key = 'name', 'name'
    order = [('-' + c if sort.startswith('-') else c) for c in PRODUCT_SORTS[sort_key]]
    page = Paginator(products.order_by(*order, 'pk'), PRODUCTS_PER_PAGE).get_page(request.GET.get('page'))
    expiring = stock_intel.expiring_product_ids([p.pk for p in page])
    product_data = [{'product': p, 'stock': p.stock, 'low': p.stock <= p.reorder_level,
                     'status': stock_intel.stock_status(p.stock, p.reorder_level),
                     'expiring': p.pk in expiring}
                    for p in page]
    # Keep the search and filters on the page links; sort links keep everything but the sort.
    params = request.GET.copy()
    params.pop('page', None)
    sort_params = params.copy()
    sort_params.pop('sort', None)
    user = request.user
    columns = [('sku', 'SKU'), ('name', 'Product'), ('category', 'Category'), ('supplier', 'Supplier'),
               ('stock', 'Stock'), ('price', 'Unit price')]
    show_cost = _role(user) in COST_ROLES
    if show_cost:
        columns.append(('cost', 'Cost price'))
    columns.append(('reorder', 'Reorder at'))
    return render(request, 'products/list.html', {
        'product_data': product_data, 'page': page, 'query': params.urlencode(),
        'sort_query': sort_params.urlencode(), 'sort': sort, 'columns': columns,
        'categories': Category.objects.all(), 'suppliers': Supplier.objects.order_by('name'),
        'q': q, 'selected_cat': category_id, 'selected_supplier': supplier_id,
        'stock_status': stock_status, 'active': active,
        'stock_choices': [('healthy', 'Healthy'), ('low', 'Low stock'), ('out', 'Out of stock'),
                          ('expiring', f'Batch expiring ≤ {stock_intel.EXPIRY_DAYS} days')],
        'show_cost': show_cost,
        'can_add': _may_open(user, 'product_add'),
        'can_edit': _may_open(user, 'product_edit'),
        'can_adjust': _may_open(user, 'stock_adjust'),
        'can_movements': _may_open(user, 'stock_movements'),
        'can_import': user.is_staff and _role(user) == 'admin',
        'filtered': bool(q or category_id or supplier_id or stock_status or active),
    })


@login_required
@role_required('admin', 'warehouse')
def product_add(request):
    form = ProductForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Product added successfully.')
        return redirect('product_list')
    return render(request, 'products/form.html', {'form': form, 'title': 'Add product'})


# ── STOCK LOOKUP (cashier) ────────────────────────────────────────────────────

# A batch expiring within this many days is flagged before it actually expires.
EXPIRY_SOON_DAYS = 30

# Enough rows to scan, few enough to stay instant while typing.
LOOKUP_LIMIT = 40


@login_required
@role_required('admin', 'cashier', 'manager')
def stock_lookup(request):
    """Counter lookup — is this product in stock, and is any of it expired?"""
    return render(request, 'products/stock_lookup.html', {})


@login_required
@role_required('admin', 'cashier', 'manager')
def stock_lookup_search(request):
    """JSON endpoint behind the lookup box — called on every keystroke.

    Stock and expiry are aggregated in the database rather than through the
    ``current_stock`` property, which would issue a query per product.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': [], 'query': q, 'truncated': False})

    # Closest matches first — an alphabetical list would bury the product the
    # cashier actually typed behind everything that merely contains the word.
    relevance = Case(
        When(sku__iexact=q, then=Value(0)),
        When(name__iexact=q, then=Value(1)),
        When(name__istartswith=q, then=Value(2)),
        When(sku__istartswith=q, then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )

    products = (Product.objects.filter(is_active=True)
                .filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
                .annotate(stock=Sum('stock_movements__quantity'), relevance=relevance)
                .order_by('relevance', 'name'))

    # One extra row tells us whether there were more matches than we show.
    rows = list(products[:LOOKUP_LIMIT + 1])
    truncated = len(rows) > LOOKUP_LIMIT
    rows = rows[:LOOKUP_LIMIT]

    today = timezone.localdate()
    soon = today + timedelta(days=EXPIRY_SOON_DAYS)

    # Expiry per product, for the handful of rows we are about to show.
    expiry = {}
    batches = (GRNItem.objects
               .filter(product__in=rows, expiry_date__isnull=False)
               .values('product_id')
               .annotate(earliest=Min('expiry_date'),
                         expired=Count('pk', filter=Q(expiry_date__lt=today))))
    for row in batches:
        expiry[row['product_id']] = row

    results = []
    for p in rows:
        stock = p.stock or 0
        batch = expiry.get(p.pk)
        earliest = batch['earliest'] if batch else None
        expired_batches = batch['expired'] if batch else 0

        if expired_batches:
            expiry_status = 'expired'
        elif earliest and earliest <= soon:
            expiry_status = 'expiring'
        elif earliest:
            expiry_status = 'ok'
        else:
            expiry_status = 'none'

        if stock <= 0:
            stock_status = 'out'
        elif stock <= p.reorder_level:
            stock_status = 'low'
        else:
            stock_status = 'in'

        results.append({
            'id': p.pk,
            'sku': p.sku,
            'name': p.name,
            'unit': p.unit,
            'price': f'{p.unit_price:.2f}',
            'stock': stock,
            'reorder_level': p.reorder_level,
            'stock_status': stock_status,
            'expiry_status': expiry_status,
            'expired_batches': expired_batches,
            'earliest_expiry': earliest.strftime('%d %b %Y') if earliest else '',
            'days_to_expiry': (earliest - today).days if earliest else None,
            'available': stock > 0 and expiry_status != 'expired',
            'url': reverse('product_detail', args=[p.pk]),
        })

    return JsonResponse({'results': results, 'query': q, 'truncated': truncated})


PRODUCT_MOVES_PER_PAGE = 25
BALANCE_DAYS = 90


@login_required
def product_detail(request, pk):
    from .models import Invoice, InvoiceItem
    product = get_object_or_404(Product.objects.select_related('category', 'supplier'), pk=pk)
    user = request.user
    today = timezone.localdate()
    stock = stock_by_product([product.pk])[product.pk]

    # Ledger, newest first, with an optional type filter; another site's invoice numbers stay hidden.
    mtype = request.GET.get('mtype', '')
    ledger = product.stock_movements.select_related('performed_by').order_by('-timestamp', '-pk')
    if mtype in dict(StockMovement.MOVEMENT_TYPES):
        ledger = ledger.filter(movement_type=mtype)
    else:
        mtype = ''
    moves_page = Paginator(ledger, PRODUCT_MOVES_PER_PAGE).get_page(request.GET.get('page'))
    movements = mask_other_sites(user, moves_page.object_list)
    type_totals = {r['movement_type']: r for r in product.stock_movements.values('movement_type')
                   .annotate(q=Sum('quantity'), n=Count('id'))}

    days = [today - timedelta(days=i) for i in range(BALANCE_DAYS - 1, -1, -1)]
    balance = stock_intel.balance_series(product, days)

    receipts = GRNItem.objects.filter(product=product).select_related('grn', 'grn__supplier').order_by('-grn__received_at')
    batches = [{'item': i, 'status': stock_intel.batch_status(i.expiry_date, today)} for i in receipts[:30]]

    # Dispatches only from invoices this user may see.
    dispatches = (InvoiceItem.objects.filter(product=product, invoice__in=visible_invoices(user),
                                             invoice__dispatch_status='dispatched')
                  .select_related('invoice', 'invoice__dispatched_by').order_by('-invoice__dispatched_at')[:20])

    pallets = list(Pallet.objects.filter(product=product).order_by('expiry_date', '-created_at')[:50])
    shelves = dict(PalletLocation.objects.filter(pallet__in=pallets, is_current=True)
                   .values_list('pallet_id', 'shelf__code'))
    pallet_rows = [{'pallet': p, 'shelf': shelves.get(p.pk), 'status': stock_intel.batch_status(p.expiry_date, today)}
                   for p in pallets]

    params = request.GET.copy()
    params.pop('page', None)
    status = stock_intel.stock_status(stock, product.reorder_level)
    show_cost = _role(user) in COST_ROLES
    return render(request, 'products/detail.html', {
        'product': product,
        'current_stock': stock,
        'status': status, 'status_label': stock_intel.STATUS_LABELS[status],
        'expiring': any(b['status'] == 'expiring' for b in batches),
        'expired': any(b['status'] == 'expired' for b in batches),
        'show_cost': show_cost,
        'stock_value': stock * product.cost_price if show_cost else None,
        'margin': (float((product.unit_price - product.cost_price) / product.unit_price * 100)
                   if show_cost and product.unit_price and product.cost_price else None),
        'movements': movements, 'moves_page': moves_page, 'mtype': mtype, 'moves_query': params.urlencode(),
        'type_choices': StockMovement.MOVEMENT_TYPES,
        'type_totals': [(k, label, type_totals.get(k, {'q': 0, 'n': 0})) for k, label in StockMovement.MOVEMENT_TYPES],
        'receipt_count': receipts.count(), 'batches': batches,
        'dispatches': dispatches, 'pallet_rows': pallet_rows, 'pallet_count': Pallet.objects.filter(product=product).count(),
        'alerts': product.alerts.filter(is_resolved=False).order_by('-created_at'),
        'expiry_days': stock_intel.EXPIRY_DAYS,
        'chart_data': {'balance': {'type': 'line', 'labels': [d.strftime('%d %b') for d in days],
                                   'datasets': [{'label': 'Stock on hand', 'data': balance}],
                                   'reference': {'label': 'Reorder level', 'value': product.reorder_level}}},
        'can_edit': _may_open(user, 'product_edit'),
        'can_adjust': _may_open(user, 'stock_adjust'),
        'can_movements': _may_open(user, 'stock_movements'),
        'can_grn': _may_open(user, 'grn_detail'),
        'can_pallet': _may_open(user, 'pallet_list'),
    })


@login_required
@role_required('admin', 'finance')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if form.is_valid():
        form.save()
        messages.success(request, 'Product updated.')
        return redirect('product_detail', pk=pk)
    return render(request, 'products/form.html', {'form': form, 'title': 'Edit product', 'product': product})


# ── SUPPLIERS ─────────────────────────────────────────────────────────────────

@login_required
def supplier_list(request):
    suppliers = Supplier.objects.annotate(product_count=Count('products'))
    return render(request, 'suppliers/list.html', {'suppliers': suppliers})


@login_required
@role_required('admin')
def supplier_add(request):
    form = SupplierForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Supplier added.')
        return redirect('supplier_list')
    return render(request, 'suppliers/form.html', {'form': form})


# ── CATEGORIES ────────────────────────────────────────────────────────────────

@login_required
def category_list(request):
    cats = Category.objects.annotate(product_count=Count('products'))
    return render(request, 'categories/list.html', {'categories': cats})


@login_required
@role_required('admin')
def category_add(request):
    form = CategoryForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Category added.')
        return redirect('category_list')
    return render(request, 'categories/form.html', {'form': form})


# ── GRN (STOCK RECEIVING) ─────────────────────────────────────────────────────

@login_required
@role_required('admin', 'warehouse', 'wms_operator')
def grn_list(request):
    grns = GoodsReceivedNote.objects.select_related('supplier', 'received_by').order_by('-received_at')
    return render(request, 'grn/list.html', {'grns': grns})


@login_required
@role_required('admin', 'warehouse', 'wms_operator')
def grn_add(request):
    form = GRNForm(request.POST or None)
    formset = GRNItemFormSet(request.POST or None)
    if form.is_valid() and formset.is_valid():
        with transaction.atomic():
            grn = form.save(commit=False)
            grn.grn_number = _gen_grn_number()
            grn.received_by = request.user
            grn.save()
            items = formset.save(commit=False)
            for item in items:
                item.grn = grn
                item.batch_number = _gen_batch_number()
                item.unit_cost = 0
                item.save()
                StockMovement.objects.create(
                    product=item.product,
                    movement_type='in',
                    quantity=item.quantity_received,
                    reference=grn.grn_number,
                    batch_number=item.batch_number,
                    expiry_date=item.expiry_date,
                    performed_by=request.user,
                )
                check_and_create_alerts(item.product)
        messages.success(request, f'GRN {grn.grn_number} saved. Stock updated.')
        return redirect('grn_detail', pk=grn.pk)
    return render(request, 'grn/form.html', {
        'form': form,
        'formset': formset,
        'grn_preview': _gen_grn_number(),
        'products_json': json.dumps(list(
            Product.objects.filter(is_active=True)
            .values('id', 'name', 'sku', 'supplier_id')
            .order_by('name')
        )),
    })


@login_required
def grn_detail(request, pk):
    grn = get_object_or_404(GoodsReceivedNote, pk=pk)
    return render(request, 'grn/detail.html', {'grn': grn})


# ── SALES / POS ───────────────────────────────────────────────────────────────

@login_required
def sale_list(request):
    sales = Sale.objects.select_related('cashier').order_by('-created_at')
    return render(request, 'sales/list.html', {'sales': sales})


@login_required
def sale_new(request):
    form = SaleForm(request.POST or None)
    formset = SaleItemFormSet(request.POST or None)
    errors = []
    if form.is_valid() and formset.is_valid():
        with transaction.atomic():
            sale = form.save(commit=False)
            sale.cashier = request.user
            sale.save()
            items = formset.save(commit=False)
            for item in items:
                if item.quantity <= 0:
                    continue
                # Check stock
                if item.product.current_stock < item.quantity:
                    errors.append(f"Insufficient stock for {item.product.name}. Available: {item.product.current_stock}")
                    transaction.set_rollback(True)
                    break
                item.sale = sale
                item.save()
                StockMovement.objects.create(
                    product=item.product,
                    movement_type='out',
                    quantity=-item.quantity,
                    reference=sale.sale_number,
                    performed_by=request.user,
                )
                check_and_create_alerts(item.product)
            if not errors:
                sale.calculate_total()
                messages.success(request, f'Sale {sale.sale_number} recorded. Total: SAT${sale.total_amount}')
                return redirect('sale_detail', pk=sale.pk)
    return render(request, 'sales/form.html', {'form': form, 'formset': formset, 'errors': errors})


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'sales/detail.html', {'sale': sale})


# ── STOCK MOVEMENTS & ADJUSTMENTS ─────────────────────────────────────────────

MOVEMENTS_PER_PAGE = 50


def _parse_day(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@login_required
@role_required('admin', 'warehouse')
def stock_movements(request):
    """The stock ledger as a timeline, filterable by product, type, user and date."""
    from django.contrib.auth.models import User
    from .models import Invoice
    user = request.user
    g = request.GET
    q = g.get('q', '').strip()
    mtype = g.get('type', '') if g.get('type', '') in dict(StockMovement.MOVEMENT_TYPES) else ''
    first, last = _parse_day(g.get('from', '')), _parse_day(g.get('to', ''))
    if first and last and first > last:
        first, last = last, first
    product = None
    if g.get('product', '').isdigit():
        product = Product.objects.filter(pk=g['product']).first()
    who = g.get('user', '') if g.get('user', '').isdigit() else ''

    moves = StockMovement.objects.select_related('product', 'performed_by')
    if product:
        moves = moves.filter(product=product)
    if q:
        by_ref = Q(reference__icontains=q)
        if not sees_all_sites(user):
            # A reference search must not confirm another site's invoice numbers.
            hidden = Invoice.objects.exclude(pk__in=visible_invoices(user).values('pk')).values('invoice_number')
            by_ref &= ~Q(reference__in=hidden)
        moves = moves.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q)
                             | Q(batch_number__icontains=q) | by_ref)
    if mtype:
        moves = moves.filter(movement_type=mtype)
    if first:
        moves = moves.filter(timestamp__date__gte=first)
    if last:
        moves = moves.filter(timestamp__date__lte=last)
    if who:
        moves = moves.filter(performed_by_id=who)

    summary = moves.aggregate(n=Count('id'), units_in=Sum('quantity', filter=Q(quantity__gt=0)),
                              units_out=Sum('quantity', filter=Q(quantity__lt=0)))
    page = Paginator(moves.order_by('-timestamp', '-pk'), MOVEMENTS_PER_PAGE).get_page(g.get('page'))
    params = g.copy()
    params.pop('page', None)
    return render(request, 'stock/movements.html', {
        'movements': mask_other_sites(user, page.object_list), 'page': page, 'query': params.urlencode(),
        'q': q, 'mtype': mtype, 'first': first, 'last': last, 'product': product, 'who': who,
        'type_choices': StockMovement.MOVEMENT_TYPES,
        'users': User.objects.filter(pk__in=StockMovement.objects.values('performed_by')).order_by('first_name', 'username'),
        'summary': summary, 'filtered': bool(q or mtype or first or last or product or who),
        'today': timezone.localdate(),
    })


@login_required
@role_required('admin', 'manager', 'warehouse')
def stock_intelligence(request):
    """Stock Intelligence workspace: stock health, movement trends, rankings and adjustments."""
    from . import dashboard as figures
    f = figures.read_filters(request)
    data = stock_intel.build(f)
    data['recent_adjustments'] = mask_other_sites(request.user, data['recent_adjustments'])
    cat_q = f'&category={f.category.pk}' if f.category else ''
    user = request.user
    products = reverse('product_list')
    data.update({
        'filters': f, 'today': timezone.localdate(), 'expiry_days': stock_intel.EXPIRY_DAYS,
        'categories': Category.objects.order_by('name'),
        'range_choices': [('7', '7 days'), ('30', '30 days'), ('90', '90 days'), ('365', '12 months')],
        'links': {
            'healthy': f'{products}?stock=healthy{cat_q}',
            'low': f'{products}?stock=low{cat_q}',
            'out': f'{products}?stock=out{cat_q}',
            'expiring': f'{products}?stock=expiring{cat_q}',
            'alerts': reverse('alert_list') + '?status=open',
            'discrepancy': reverse('alert_list') + '?type=discrepancy&status=open',
            'grns': reverse('grn_list') if _may_open(user, 'grn_list') else None,
            'ledger': reverse('stock_movements') if _may_open(user, 'stock_movements') else None,
        },
    })
    return render(request, 'stock/intelligence.html', data)


@login_required
@role_required('admin', 'warehouse')
def stock_adjust(request):
    initial = {}
    if request.method == 'GET' and request.GET.get('product', '').isdigit():
        initial['product'] = request.GET['product']
    form = StockAdjustForm(request.POST or None, initial=initial)
    if form.is_valid():
        movement = form.save(commit=False)
        movement.performed_by = request.user
        movement.save()
        check_and_create_alerts(movement.product)
        messages.success(request, 'Stock adjustment recorded.')
        return redirect('stock_movements')
    return render(request, 'stock/adjust.html', {'form': form})


# ── ALERTS ────────────────────────────────────────────────────────────────────

ALERTS_PER_PAGE = 50
ALERT_NEW_DAYS = 7          # "new" on the alerts page = raised in the last week
ALERT_RESOLVED_DAYS = 30    # "recently resolved" = resolved in the last 30 days


def _alerts_with_stock(alerts):
    return alerts.annotate(stock=Coalesce(Sum('product__stock_movements__quantity'), 0))


@login_required
def alert_list(request):
    g = request.GET
    alerts = _alerts_with_stock(StockAlert.objects.select_related('product', 'resolved_by'))
    alert_type = g.get('type', '')
    status = g.get('status', '')
    q = g.get('q', '').strip()
    if alert_type in dict(StockAlert.ALERT_TYPES):
        alerts = alerts.filter(alert_type=alert_type)
    else:
        alert_type = ''
    if status in ('open', 'resolved'):
        alerts = alerts.filter(is_resolved=(status == 'resolved'))
    elif status == 'critical':
        alerts = alerts.filter(is_resolved=False, stock__lte=0)
    else:
        status = ''
    if q:
        alerts = alerts.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q))

    now = timezone.now()
    open_all = _alerts_with_stock(StockAlert.objects.filter(is_resolved=False))
    open_by_type = dict(StockAlert.objects.filter(is_resolved=False).values_list('alert_type').annotate(n=Count('id')))
    summary = {
        'outstanding': sum(open_by_type.values()),
        'critical': open_all.filter(stock__lte=0).count(),
        'new': StockAlert.objects.filter(created_at__gte=now - timedelta(days=ALERT_NEW_DAYS)).count(),
        'resolved': StockAlert.objects.filter(is_resolved=True,
                                              resolved_at__gte=now - timedelta(days=ALERT_RESOLVED_DAYS)).count(),
        'by_type': [(k, label, open_by_type.get(k, 0)) for k, label in StockAlert.ALERT_TYPES],
    }
    page = Paginator(alerts.order_by('is_resolved', '-created_at', '-pk'), ALERTS_PER_PAGE).get_page(g.get('page'))
    params = g.copy()
    params.pop('page', None)
    return render(request, 'alerts/list.html', {
        'alerts': page.object_list, 'page': page, 'query': params.urlencode(),
        'alert_type': alert_type, 'status': status, 'q': q,
        'type_choices': StockAlert.ALERT_TYPES, 'summary': summary,
        'new_days': ALERT_NEW_DAYS, 'resolved_days': ALERT_RESOLVED_DAYS,
        'can_resolve': _may_open(request.user, 'alert_resolve'),
        'filtered': bool(alert_type or status or q),
    })


@login_required
def alert_detail(request, pk):
    alert = get_object_or_404(StockAlert.objects.select_related('product', 'resolved_by'), pk=pk)
    product = alert.product
    today = timezone.localdate()
    stock = stock_by_product([product.pk])[product.pk]
    batches = [{'item': i, 'status': stock_intel.batch_status(i.expiry_date, today)}
               for i in GRNItem.objects.filter(product=product, expiry_date__isnull=False)
               .select_related('grn').order_by('expiry_date')[:10]]
    return render(request, 'alerts/detail.html', {
        'alert': alert, 'product': product, 'stock': stock,
        'status': stock_intel.stock_status(stock, product.reorder_level),
        'movements': mask_other_sites(request.user, product.stock_movements.select_related('performed_by')
                                      .order_by('-timestamp', '-pk')[:10]),
        'batches': batches,
        'others': product.alerts.exclude(pk=alert.pk).order_by('is_resolved', '-created_at')[:10],
        'can_resolve': _may_open(request.user, 'alert_resolve'),
        'can_adjust': _may_open(request.user, 'stock_adjust'),
        'can_grn': _may_open(request.user, 'grn_detail'),
    })


@login_required
@role_required('admin', 'warehouse')
def alert_resolve(request, pk):
    """Resolve an alert. POST only: following a link must never change data."""
    from django.utils.http import url_has_allowed_host_and_scheme
    alert = get_object_or_404(StockAlert, pk=pk)
    if request.method != 'POST':
        return redirect('alert_detail', pk=pk)
    if alert.is_resolved:
        messages.info(request, 'That alert was already resolved.')
    else:
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.save()
        messages.success(request, 'Alert marked as resolved.')
    nxt = request.POST.get('next', '')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return redirect(nxt)
    return redirect('alert_list')


# ── REPORTS ───────────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager')
def reports(request):
    products = with_stock(Product.objects.filter(is_active=True))
    top_sellers = SaleItem.objects.values('product__name').annotate(
        total_qty=Sum('quantity'), total_rev=Sum('unit_price')
    ).order_by('-total_qty')[:10]

    # Monthly sales last 6 months
    monthly = []
    for i in range(5, -1, -1):
        d = timezone.localdate().replace(day=1) - timedelta(days=i*30)
        amt = Sale.objects.filter(created_at__year=d.year, created_at__month=d.month).aggregate(t=Sum('total_amount'))['t'] or 0
        monthly.append({'month': d.strftime('%b %Y'), 'amount': float(amt)})

    low_stock = Paginator(products.filter(stock__lte=F('reorder_level')).order_by('name', 'pk'),
                          PRODUCTS_PER_PAGE).get_page(request.GET.get('low_page'))
    expiring_soon = GRNItem.objects.filter(
        expiry_date__lte=timezone.localdate() + timedelta(days=30),
        expiry_date__gte=timezone.localdate()
    ).select_related('product')

    context = {
        'total_stock_value': total_stock_value(),
        'top_sellers': top_sellers,
        'monthly_json': json.dumps(monthly),
        'low_stock': low_stock,
        'expiring_soon': expiring_soon,
        'total_sales': Sale.objects.aggregate(t=Sum('total_amount'))['t'] or 0,
        'total_sales_count': Sale.objects.count(),
    }
    return render(request, 'reports/index.html', context)


@login_required
@role_required('admin')
def export_stock_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="ah_liki_stock.csv"'
    writer = csv.writer(response)
    writer.writerow(['SKU', 'Product', 'Category', 'Supplier', 'Current Stock', 'Unit', 'Reorder Level', 'Cost Price', 'Stock Value (SAT$)'])
    for p in with_stock(Product.objects.filter(is_active=True).select_related('category', 'supplier')):
        writer.writerow([p.sku, p.name, p.category or '', p.supplier or '', p.stock,
                         p.unit, p.reorder_level, p.cost_price, p.stock * p.cost_price])
    return response


@login_required
@role_required('admin')
def export_sales_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="ah_liki_sales.csv"'
    writer = csv.writer(response)
    writer.writerow(['Sale No.', 'Date', 'Cashier', 'Customer', 'Payment', 'Total (SAT$)'])
    for s in Sale.objects.select_related('cashier').order_by('-created_at'):
        writer.writerow([s.sale_number, s.created_at.strftime('%d/%m/%Y %H:%M'),
                         s.cashier.get_full_name() or s.cashier.username if s.cashier else '',
                         s.customer_name, s.payment_method, s.total_amount])
    return response


# ── API ───────────────────────────────────────────────────────────────────────

@login_required
def api_product_lookup(request, sku):
    try:
        p = Product.objects.get(Q(sku=sku) | Q(barcode=sku))
        return JsonResponse({'id': p.pk, 'name': p.name, 'sku': p.sku,
                             'unit_price': str(p.unit_price), 'stock': p.current_stock, 'unit': p.unit})
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)


# ── USER PROFILE & MANAGEMENT ─────────────────────────────────────────────────

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

@login_required
def profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    return render(request, 'users/profile.html', {'profile': profile})


@login_required
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Password changed successfully.')
        return redirect('profile')
    return render(request, 'users/change_password.html', {'form': form})


@login_required
@role_required('admin')
def user_list(request):
    from django.contrib.auth.models import User
    users = User.objects.select_related('profile').all().order_by('username')
    return render(request, 'users/list.html', {'users': users})


@login_required
@role_required('admin')
def user_add(request):
    from django.contrib.auth.models import User
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        role = request.POST.get('role', 'cashier')
        if not username or not password:
            messages.error(request, 'Username and password are required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
        else:
            u = User.objects.create_user(username=username, password=password,
                first_name=first_name, last_name=last_name, email=email)
            new_profile = UserProfile.objects.get(user=u)
            new_profile.role = role
            new_profile.set_sites(request.POST.getlist('sites'))
            new_profile.save()
            messages.success(request, f'User "{username}" created successfully.')
            return redirect('user_list')
    return render(request, 'users/add.html', {'all_sites': SITES, 'chosen_sites': request.POST.getlist('sites')})


@login_required
@role_required('admin')
def user_edit(request, pk):
    from django.contrib.auth.models import User
    u = get_object_or_404(User, pk=pk)
    profile, _ = UserProfile.objects.get_or_create(user=u)
    if request.method == 'POST':
        u.first_name = request.POST.get('first_name', '').strip()
        u.last_name = request.POST.get('last_name', '').strip()
        u.email = request.POST.get('email', '').strip()
        u.is_active = 'is_active' in request.POST
        u.save()
        profile.role = request.POST.get('role', 'cashier')
        profile.set_sites(request.POST.getlist('sites'))
        profile.save()
        new_pw = request.POST.get('new_password', '').strip()
        if new_pw:
            u.set_password(new_pw)
            u.save()
        messages.success(request, f'User "{u.username}" updated.')
        return redirect('user_list')
    return render(request, 'users/edit.html', {'u': u, 'profile': profile,
                                               'all_sites': SITES, 'chosen_sites': profile.site_list})


# ── INVOICE UPLOAD (replaces POS) ─────────────────────────────────────────────

from .models import Quote, QuoteItem, Invoice, InvoiceItem
from .forms import InvoiceUploadForm
from .catalogue_match import annotate_items, compare_item, CatalogueIndex
from decimal import Decimal
import uuid


def _parse_ahliki_invoice(file_obj):
    """Extract fields and line items from an Ah Liki Wholesale PDF invoice using pdfplumber."""
    import pdfplumber
    import re

    result = {}

    with pdfplumber.open(file_obj) as pdf:
        pages = pdf.pages
        full_text = '\n'.join(page.extract_text() or '' for page in pages)

        # ── Line items — try pdfplumber table extraction first ────────
        extracted_items = []
        for page in pages:
            try:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or not row[0]:
                            continue
                        cell0 = str(row[0]).strip()
                        if not re.match(r'^AL\d+$', cell0, re.IGNORECASE):
                            continue
                        sku = cell0.upper()
                        description = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                        qty_cell = str(row[2]).strip() if len(row) > 2 and row[2] else ''
                        price_cell = str(row[3]).strip() if len(row) > 3 and row[3] else ''

                        qty_m = re.match(r'(\d+)', qty_cell)
                        qty = int(qty_m.group(1)) if qty_m else 1
                        unit = re.sub(r'^\d+\s*', '', qty_cell).strip()

                        price = re.sub(r'[,$\s]', '', price_cell)
                        try:
                            unit_price = float(price)
                        except (ValueError, TypeError):
                            unit_price = 0.0

                        extracted_items.append({
                            'sku': sku,
                            'description': description,
                            'quantity': qty,
                            'unit': unit,
                            'unit_price': str(round(unit_price, 2)),
                        })
            except Exception:
                pass

        # ── Fallback: regex on raw text ───────────────────────────────
        if not extracted_items:
            # Each item line looks like:
            # AL10000876 Farm Frite Seasoned Wedges Skin On 4*2.5Kg 4 CASE $88.18 $352.72
            item_re = re.compile(
                r'^(AL\d+)\s+(.+?)\s+(\d+)\s+([A-Z][A-Z0-9\-]*)\s+\$?([\d,]+\.\d{2})',
                re.MULTILINE | re.IGNORECASE,
            )
            for m in item_re.finditer(full_text):
                extracted_items.append({
                    'sku': m.group(1).upper(),
                    'description': m.group(2).strip(),
                    'quantity': int(m.group(3)),
                    'unit': m.group(4).upper(),
                    'unit_price': m.group(5).replace(',', ''),
                })

    result['items'] = extracted_items

    # ── Invoice number ────────────────────────────────────────
    m = re.search(r'Sales Invoice\s+(\w+)', full_text, re.IGNORECASE)
    if m:
        result['invoice_number'] = m.group(1)

    # ── Sales territory ───────────────────────────────────────
    m = re.search(r'Sales Territory:\s*(\w+)', full_text, re.IGNORECASE)
    if m:
        result['sales_territory'] = m.group(1)

    # ── Valid-to date, salesperson, payment terms ─────────────
    m = re.search(
        r'(\d{1,2}/\d{2}/\d{2})\s+([A-Z][A-Z]+)\s+(Net\s+\d+\s+days?)',
        full_text, re.IGNORECASE,
    )
    if m:
        date_str = m.group(1)
        result['salesperson'] = m.group(2).title()
        result['payment_terms'] = m.group(3).strip()
        parts = date_str.split('/')
        if len(parts) == 3:
            d, mo, yr = parts
            result['due_date'] = f"20{yr}-{mo.zfill(2)}-{d.zfill(2)}"

    # ── Customer name ─────────────────────────────────────────
    m = re.search(r'([A-Z][A-Z &\'\-]+?)\s{2,}Ah Liki Wholesale', full_text)
    if not m:
        m = re.search(r'^(.+?)\s+Ah Liki Wholesale', full_text, re.MULTILINE)
    if m:
        candidate = re.sub(r'Sales Territory:\s*\w+\s*', '', m.group(1), flags=re.IGNORECASE).strip()
        if len(candidate) > 2:
            result['customer_name'] = candidate.title()
    if 'customer_name' not in result:
        m = re.search(r'Sales Territory:\s*\w+\s*\n([A-Z][A-Z\s]+)', full_text)
        if m:
            result['customer_name'] = m.group(1).strip().split('\n')[0].strip().title()

    # ── Totals ────────────────────────────────────────────────
    m = re.search(r'Total\s*\$\s*Incl\.?\s*VAT\s+\$?([\d,]+\.?\d*)', full_text, re.IGNORECASE)
    if m:
        result['total_amount'] = m.group(1).replace(',', '')

    m = re.search(r'15%\s*VAT\s+\$?([\d,]+\.?\d*)', full_text, re.IGNORECASE)
    if m:
        result['tax_amount'] = m.group(1).replace(',', '')

    result['payment_method'] = 'credit'

    return result


@login_required
@role_required('admin', 'cashier')
def invoice_parse_pdf(request):
    """AJAX endpoint — parse uploaded PDF and return extracted fields as JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    pdf_file = request.FILES.get('pdf')
    if not pdf_file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    if not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'File must be a PDF'}, status=400)

    try:
        data = _parse_ahliki_invoice(pdf_file)
        # Compare SKU, description and unit of every line against the catalogue
        annotate_items(data.get('items', []))
        return JsonResponse({'success': True, 'data': data})
    except Exception as exc:
        return JsonResponse({'success': False, 'data': {}, 'error': str(exc)})


@login_required
@role_required('admin', 'cashier')
def invoice_upload(request):
    """Simple invoice upload view — upload the Ah Liki PDF invoice into the system."""
    sites = user_sites(request.user)
    if request.method == 'POST':
        form = InvoiceUploadForm(request.POST, request.FILES)
        site = sites[0] if len(sites) == 1 else request.POST.get('site', '')
        if site not in sites:
            messages.error(request, 'Pick the site this invoice belongs to.' if sites else
                           'You have no site yet, so you cannot upload invoices. Ask an admin to give you one.')
        elif form.is_valid():
            invoice = form.save(commit=False)
            invoice.site = site
            invoice.cashier = request.user
            invoice.dispatch_status = 'pending'
            invoice.save()

            # Create InvoiceItems from the extracted items JSON. The browser's
            # match is only a preview — re-compare SKU/description/unit here so
            # a tampered or stale payload can't attach the wrong product.
            unmatched = 0
            flagged = []
            raw_items = request.POST.get('extracted_items', '').strip()
            if raw_items:
                import json as _json
                try:
                    item_list = _json.loads(raw_items)
                except (ValueError, TypeError):
                    item_list = []  # Bad JSON — just skip items
                index = CatalogueIndex()
                by_pk = {p.pk: p for p in index.products}
                for it in item_list:
                    if not isinstance(it, dict):
                        continue
                    match = compare_item(it, index=index)
                    product = by_pk.get(match['product_id']) if match['matched'] else None
                    if not product:
                        unmatched += 1
                        continue
                    try:
                        unit_price = Decimal(str(it.get('unit_price', product.unit_price)))
                    except Exception:
                        unit_price = product.unit_price
                    try:
                        quantity = int(it.get('quantity', 1))
                    except (TypeError, ValueError):
                        quantity = 1
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=product,
                        quantity=max(quantity, 1),
                        unit_price=unit_price,
                        discount_percent=Decimal('0'),
                    )
                    fm = match['field_matches']
                    if fm.get('unit') in ('differs', 'close'):
                        flagged.append(f'{product.name} — unit "{it.get("unit", "")}" '
                                       f'vs catalogue "{product.unit}"')
                    elif fm.get('description') == 'differs':
                        flagged.append(f'{product.name} — description differs from the catalogue')
                    elif match.get('ambiguous'):
                        flagged.append(f'{product.name} — several catalogue products fit this line')

            item_count = invoice.items.count()
            suffix = f' {item_count} item{"s" if item_count != 1 else ""} matched.' if item_count else ' PDF stored as reference.'
            messages.success(request, f'Invoice {invoice.invoice_number} uploaded and sent to dispatch.{suffix}')
            if unmatched:
                messages.warning(
                    request,
                    f'{unmatched} line{"s" if unmatched != 1 else ""} had no catalogue match '
                    'and were not added as line items — they remain visible on the PDF.')
            for note in flagged[:10]:
                messages.warning(request, f'Catalogue mismatch: {note}')
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceUploadForm()
    return render(request, 'pos/invoice_upload.html',
                  {'form': form, 'upload_sites': sites, 'chosen_site': request.POST.get('site', '')})



def quote_new(request):
    products = with_stock(Product.objects.filter(is_active=True)).order_by('name')
    if request.method == 'POST':
        import json as _json
        data = _json.loads(request.body)
        cart = data.get('cart', [])
        if not cart:
            return JsonResponse({'error': 'Cart is empty'}, status=400)
        quote = Quote.objects.create(
            quote_number=gen_number('QTE'),
            cashier=request.user,
            customer_name=data.get('customer_name', ''),
            account_number=data.get('account_number', ''),
            notes=data.get('notes', ''),
            valid_until=data.get('valid_until') or None,
        )
        for line in cart:
            product = Product.objects.get(pk=line['product_id'])
            QuoteItem.objects.create(quote=quote, product=product, quantity=int(line['qty']),
                                     unit_price=product.unit_price,
                                     discount_percent=Decimal(str(line.get('discount', 0))))
        quote.calculate_total()
        return JsonResponse({'success': True, 'quote_number': quote.quote_number, 'quote_id': quote.pk})
    return render(request, 'pos/pos.html', {'products': products, 'mode': 'quote'})


@login_required
def quote_detail(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    return render(request, 'pos/quote_detail.html', {'quote': quote})


@login_required
def quote_convert(request, pk):
    """Convert a quote to an invoice — one click."""
    quote = get_object_or_404(Quote, pk=pk)
    if quote.status == 'converted':
        messages.warning(request, 'This quote has already been converted.')
        return redirect('quote_detail', pk=pk)
    with transaction.atomic():
        invoice = Invoice.objects.create(
            invoice_number=gen_number('INV'),
            site=next(iter(user_sites(request.user)), ''),
            cashier=request.user,
            customer_name=quote.customer_name,
            account_number=quote.account_number,
            notes=quote.notes,
            dispatch_status='pending',
        )
        for qi in quote.items.all():
            InvoiceItem.objects.create(
                invoice=invoice, product=qi.product,
                quantity=qi.quantity, unit_price=qi.unit_price,
                discount_percent=qi.discount_percent,
            )
        invoice.calculate_total()
        quote.status = 'converted'
        quote.converted_to = invoice
        quote.save()
    messages.success(request, f'Quote converted to Invoice {invoice.invoice_number}. Sent to warehouse for dispatch.')
    return redirect('invoice_detail', pk=invoice.pk)


# ── WAREHOUSE DISPATCH ─────────────────────────────────────────────────────────

def _picked_sites(request):
    """The sites picked on Warehouse Dispatch; none picked means all of them.

    Remembered for the login session, so Back to Dispatch, Sync now and the menu keep the filter.
    """
    options = user_sites(request.user) + (['OTHER'] if sees_all_sites(request.user) else [])
    if 'site' in request.GET:
        asked = {value.upper() for value in request.GET.getlist('site')}
        request.session['dispatch_sites'] = [site for site in options if site in asked]
    # Re-checked each time: access may have changed since the sites were picked.
    return [site for site in request.session.get('dispatch_sites', []) if site in options]


def _filter_sites(invoices, picked):
    """Only invoices of the picked sites. OTHER is everything outside the known sites, e.g. uploads."""
    if not picked:
        return invoices
    wanted = Q(site__in=picked)
    if 'OTHER' in picked:
        wanted |= ~Q(site__in=SITES)
    return invoices.filter(wanted)


def _site_options(user, picked, pending=None, dispatched=None):
    """The filter's options for this user, each with its pending and dispatched totals.

    `pending` and `dispatched` are the tabs' invoices before the site filter (so with their dates),
    so each site's number is what the tab would show for it.
    """
    codes = user_sites(user) + (['OTHER'] if sees_all_sites(user) else [])
    totals = {site: {'pending': 0, 'dispatched': 0} for site in codes}
    visible = visible_invoices(user)
    for status, invoices in (('pending', pending), ('dispatched', dispatched)):
        invoices = visible.filter(dispatch_status=status) if invoices is None else invoices
        for row in invoices.order_by().values('site').annotate(n=Count('pk', distinct=True)):
            site = row['site'] if row['site'] in SITES else 'OTHER'
            if site in totals:
                totals[site][status] += row['n']
    return [{'code': site, 'label': 'Other / no site' if site == 'OTHER' else site, 'picked': site in picked, **n}
            for site, n in totals.items()
            if site != 'OTHER' or site in picked or any(n.values())]


DISPATCH_PER_PAGE = 30


def _search_log(invoices, q='', date_from='', date_to=''):
    """The Dispatch Log's search and dates, shared by the page and its CSV export."""
    from datetime import datetime
    for value, lookup in ((date_from, 'dispatched_at__date__gte'), (date_to, 'dispatched_at__date__lte')):
        try:
            invoices = invoices.filter(**{lookup: datetime.strptime(value, '%Y-%m-%d').date()})
        except ValueError:
            pass
    if q:
        invoices = invoices.filter(
            Q(invoice_number__icontains=q) | Q(customer_name__icontains=q) | Q(truck_plate__icontains=q)
            | Q(dispatched_by__first_name__icontains=q) | Q(dispatched_by__last_name__icontains=q)
            | Q(dispatched_by__username__icontains=q))
    return invoices


PENDING_DATES = (('today', 'Today'), ('yesterday', 'Yesterday'), ('week', 'Last 7 days'), ('all', 'All dates'))


def _day(value):
    from datetime import datetime
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _pending_dates(params):
    """The Pending tab's date filter: ('today' | 'yesterday' | 'week' | 'all' | 'range', first, last).

    Today is the default. Dates are the day the invoice reached the IMS (the list's Date column).
    """
    when = params.get('when', 'today')
    today = timezone.localdate()
    if when == 'range':
        first, last = _day(params.get('pfrom', '')), _day(params.get('pto', ''))
        if first or last:
            return when, first, last
        when = 'all'
    ranges = {'today': (today, today), 'yesterday': (today - timedelta(days=1), today - timedelta(days=1)),
              'week': (today - timedelta(days=6), today), 'all': (None, None)}
    if when not in ranges:
        when = 'today'
    return (when, *ranges[when])


def _between(invoices, field, first, last):
    if first:
        invoices = invoices.filter(**{f'{field}__date__gte': first})
    if last:
        invoices = invoices.filter(**{f'{field}__date__lte': last})
    return invoices


def _query(request, drop=(), **extra):
    """The current query string without the `drop` parameters, plus `extra`."""
    params = request.GET.copy()
    for name in drop:
        params.pop(name, None)
    for name, value in extra.items():
        params[name] = value
    return params


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def warehouse_dispatch_list(request):
    """Invoices pending dispatch and the dispatch log, each 30 to a page.

    Search runs on the server, over every page. Each tab pages on its own and its links keep the
    other tab's page and searches.
    """
    q = request.GET.get('q', '').strip()
    lq = request.GET.get('lq', '').strip()
    log_from = request.GET.get('from', '').strip()
    log_to = request.GET.get('to', '').strip()
    picked = _picked_sites(request)
    when, pending_from, pending_to = _pending_dates(request.GET)

    # Thousands of POS invoices can be pending, so nothing here may cost a query per row.
    all_pending = visible_invoices(request.user).filter(dispatch_status='pending')
    if q:
        all_pending = all_pending.filter(
            Q(invoice_number__icontains=q) | Q(customer_name__icontains=q) | Q(account_number__icontains=q)
            | Q(cashier__first_name__icontains=q) | Q(cashier__last_name__icontains=q)
            | Q(cashier__username__icontains=q))
    dated_pending = _between(all_pending, 'created_at', pending_from, pending_to)
    pending = (_filter_sites(dated_pending, picked).select_related('cashier', 'ls_central')
               .annotate(item_count=Count('items')).order_by('-created_at', '-pk'))
    log_base = _search_log(visible_invoices(request.user).filter(dispatch_status='dispatched'), lq, log_from, log_to)
    dispatch_log = (_filter_sites(log_base, picked).select_related('cashier', 'dispatched_by', 'ls_central')
                    .order_by('-dispatched_at', '-pk'))

    # The date buttons, each with how many pending invoices it would show (same sites and search).
    sited = _filter_sites(all_pending, picked)
    date_options = []
    for code, label in PENDING_DATES:
        _, first, last = _pending_dates({'when': code})
        date_options.append({'code': code, 'label': label, 'on': when == code,
                             'count': _between(sited, 'created_at', first, last).count(),
                             'query': _query(request, ('when', 'pfrom', 'pto', 'page', 'tab', 'site'),
                                             when=code).urlencode()})
    today = timezone.localdate()
    log_dates = []
    for label, first, last in (('Today', today, today), ('Yesterday', today - timedelta(days=1), today - timedelta(days=1)),
                               ('Last 7 days', today - timedelta(days=6), today), ('All dates', None, None)):
        first, last = (first.isoformat() if first else ''), (last.isoformat() if last else '')
        extra = {k: v for k, v in (('from', first), ('to', last)) if v}
        log_dates.append({'label': label, 'on': (log_from, log_to) == (first, last),
                          'query': _query(request, ('from', 'to', 'log_page', 'site'), tab='log', **extra).urlencode()})

    searches = ('q', 'lq', 'from', 'to', 'when', 'pfrom', 'pto')
    return render(request, 'warehouse/dispatch_list.html', {
        'pending': pending,
        'dispatch_log': dispatch_log,
        'pending_page': Paginator(pending, DISPATCH_PER_PAGE).get_page(request.GET.get('page')),
        'log_page': Paginator(dispatch_log, DISPATCH_PER_PAGE).get_page(request.GET.get('log_page')),
        'pending_pager': {'param': 'page', 'query': _query(request, ('page', 'tab', 'site')).urlencode()},
        'log_pager': {'param': 'log_page', 'query': _query(request, ('log_page', 'site'), tab='log').urlencode()},
        'q': q, 'lq': lq, 'log_from': log_from, 'log_to': log_to,
        'when': when, 'date_options': date_options, 'log_dates': log_dates,
        'pending_from': pending_from.isoformat() if when == 'range' and pending_from else '',
        'pending_to': pending_to.isoformat() if when == 'range' and pending_to else '',
        'when_label': dict(PENDING_DATES).get(when, 'these dates'),
        'search_all_dates': _query(request, ('when', 'pfrom', 'pto', 'page', 'tab', 'site'), when='all').urlencode(),
        # A new search starts on page 1 of its own tab; the other tab keeps its place.
        'keep_for_pending': [(k, v) for k, v in _query(request, ('q', 'page', 'tab', 'site')).items()],
        'keep_for_log': [(k, v) for k, v in _query(request, ('lq', 'from', 'to', 'log_page', 'tab', 'site')).items()],
        'keep_searches': [(k, request.GET[k]) for k in searches if request.GET.get(k)],
        'clear_pending': _query(request, ('q', 'page', 'tab', 'site')).urlencode(),
        'clear_log': _query(request, ('lq', 'from', 'to', 'log_page', 'site'), tab='log').urlencode(),
        'site_options': _site_options(request.user, picked, dated_pending, log_base),
        'picked_sites': picked,
    })


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def warehouse_dispatch_detail(request, pk):
    """Show the dispatch detail for a single invoice."""
    invoice = get_visible_invoice(request.user, pk=pk)

    # Handle inline comment submission
    if request.method == 'POST' and request.POST.get('add_comment'):
        body = request.POST.get('comment_body', '').strip()
        if body:
            DispatchComment.objects.create(invoice=invoice, author=request.user, body=body)
            messages.success(request, 'Comment added.')
        return redirect('warehouse_dispatch_detail', pk=pk)

    if invoice.dispatch_status == 'pending':
        # LS Central invoices: add any lines still missing from the catalogue to Products first.
        from ls_central.sync import complete_pick_list
        added = complete_pick_list(invoice)
        if added:
            messages.info(request, f'{len(added)} product{"s" if len(added) != 1 else ""} not in the catalogue '
                                   'added to Products from this invoice: ' + ', '.join(p.sku for p in added) + '.')

    items = list(invoice.items.select_related('product').all())
    stock_map = stock_by_product([i.product_id for i in items])
    allow_no_stock = settings.DISPATCH_ALLOW_NO_STOCK
    item_data = []
    for item in items:
        stock = stock_map[item.product_id]
        item_data.append({
            'item': item,
            'current_stock': stock,
            'sufficient': stock >= item.quantity,
            'default_dispatch_qty': (item.quantity if allow_no_stock
                                     else min(item.quantity, stock) if stock > 0 else 0),
        })
    comments = invoice.comments.select_related('author').all()
    return render(request, 'warehouse/dispatch_detail.html', {
        'invoice': invoice,
        'item_data': item_data,
        'comments': comments,
        'allow_no_stock': allow_no_stock,
    })


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def warehouse_dispatch_submit(request, pk):
    """Confirm dispatch — for PDF invoices just marks dispatched; for item invoices deducts stock."""
    invoice = get_visible_invoice(request.user, pk=pk)
    if request.method != 'POST':
        return redirect('warehouse_dispatch_detail', pk=pk)

    if invoice.dispatch_status == 'dispatched':
        messages.warning(request, 'This invoice has already been dispatched.')
        return redirect('warehouse_dispatch_detail', pk=pk)

    truck_plate = request.POST.get('truck_plate', '').strip()
    if not truck_plate:
        messages.error(request, 'Truck plate number is required.')
        return redirect('warehouse_dispatch_detail', pk=pk)

    checked_item_ids = set(request.POST.getlist('checked_items'))
    items = list(invoice.items.select_related('product').all())

    # PDF-uploaded invoices have no line items — skip item validation
    if not items:
        adjustment_reason = request.POST.get('adjustment_reason', '').strip()
        with transaction.atomic():
            invoice.dispatch_status = 'dispatched'
            invoice.dispatched_by = request.user
            invoice.dispatched_at = timezone.now()
            invoice.truck_plate = truck_plate
            invoice.save(update_fields=['dispatch_status', 'dispatched_by', 'dispatched_at', 'truck_plate'])
            if adjustment_reason:
                DispatchComment.objects.create(invoice=invoice, author=request.user, body=adjustment_reason)
        messages.success(request, f'Invoice {invoice.invoice_number} dispatched successfully.')
        return redirect('warehouse_dispatch_detail', pk=pk)

    # Collect dispatcher-entered quantities (may be partial for low-stock items)
    dispatch_quantities = {}
    for item in items:
        qty_str = request.POST.get(f'dispatch_qty_{item.pk}', '').strip()
        try:
            dqty = int(qty_str)
        except (ValueError, TypeError):
            dqty = item.quantity
        dispatch_quantities[item.pk] = dqty

    stock_map = stock_by_product([i.product_id for i in items])
    errors = []
    for item in items:
        if str(item.pk) not in checked_item_ids:
            errors.append(f"{item.product.name} has not been checked off.")
        else:
            dqty = dispatch_quantities[item.pk]
            if dqty <= 0:
                errors.append(f"Dispatch quantity for {item.product.name} must be at least 1.")
            elif dqty > stock_map[item.product_id] and not settings.DISPATCH_ALLOW_NO_STOCK:
                errors.append(
                    f"Dispatch quantity for {item.product.name} ({dqty}) exceeds available stock "
                    f"({stock_map[item.product_id]} {item.product.unit})."
                )

    if errors:
        for err in errors:
            messages.error(request, err)
        return redirect('warehouse_dispatch_detail', pk=pk)

    adjustment_reason = request.POST.get('adjustment_reason', '').strip()

    with transaction.atomic():
        adjustments = []
        for item in items:
            dqty = dispatch_quantities[item.pk]
            original_qty = item.quantity
            if dqty != original_qty:
                adjustments.append(
                    f"\u2022 {item.product.name}: ordered {original_qty} {item.product.unit}, "
                    f"dispatched {dqty} {item.product.unit} "
                    f"(stock available: {stock_map[item.product_id]} {item.product.unit})"
                )
                item.quantity = dqty
                item.save(update_fields=['quantity'])
            StockMovement.objects.create(
                product=item.product,
                movement_type='out',
                quantity=-dqty,
                reference=invoice.invoice_number,
                performed_by=request.user,
            )
            check_and_create_alerts(item.product)

        invoice.dispatch_status = 'dispatched'
        invoice.dispatched_by = request.user
        invoice.dispatched_at = timezone.now()
        invoice.truck_plate = request.POST.get('truck_plate', '').strip()
        invoice.save(update_fields=['dispatch_status', 'dispatched_by', 'dispatched_at', 'truck_plate'])

        if adjustments:
            invoice.calculate_total()

        # Auto-comment recording partial dispatch details
        if adjustments:
            auto_body = "\u26a0\ufe0f Partial dispatch \u2014 quantities adjusted:\n" + "\n".join(adjustments)
            if adjustment_reason:
                auto_body += f"\n\nReason: {adjustment_reason}"
            DispatchComment.objects.create(invoice=invoice, author=request.user, body=auto_body)
        elif adjustment_reason:
            DispatchComment.objects.create(invoice=invoice, author=request.user, body=adjustment_reason)

    messages.success(request, f'Invoice {invoice.invoice_number} dispatched successfully. Stock has been updated.')
    return redirect('warehouse_dispatch_detail', pk=pk)


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def warehouse_dispatch_export(request):
    """Export the dispatch log as a CSV, with optional site/date/search filters."""
    qs = visible_invoices(request.user).filter(dispatch_status='dispatched').select_related('cashier', 'dispatched_by').order_by('-dispatched_at')

    qs = _search_log(_filter_sites(qs, _picked_sites(request)), request.GET.get('q', '').strip(),
                     request.GET.get('from', '').strip(), request.GET.get('to', '').strip())

    filename = f"dispatch_log_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Date & Time', 'Invoice #', 'Customer', 'Account #', 'Payment Method',
                     'Invoice Amount (SAT$)', 'Tax (SAT$)', 'Items', 'Checked Out By', 'Truck Plate #'])
    for inv in qs:
        dispatched_by = ''
        if inv.dispatched_by:
            dispatched_by = inv.dispatched_by.get_full_name() or inv.dispatched_by.username
        writer.writerow([
            inv.dispatched_at.strftime('%d/%m/%Y %H:%M') if inv.dispatched_at else '',
            inv.invoice_number,
            inv.customer_name or 'Walk-in',
            inv.account_number or '',
            inv.get_payment_method_display(),
            inv.total_amount,
            inv.tax_amount,
            inv.items.count(),
            dispatched_by,
            inv.truck_plate or '',
        ])
    return response


# ── INVOICES ──────────────────────────────────────────────────────────────────

@login_required
def invoice_media(request, path):
    """Uploaded files: only the exact file of an invoice the user may see."""
    if not path or not visible_invoices(request.user).filter(invoice_file=path).exists():
        raise Http404
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response['X-Content-Type-Options'] = 'nosniff'
    if not path.lower().endswith('.pdf'):
        # Anything else (say .html) could run as a page in the viewer's session.
        response['Content-Disposition'] = 'attachment'
    return response


@login_required
def invoice_list(request):
    invoices = visible_invoices(request.user).select_related('cashier').order_by('-created_at', '-pk')
    return render(request, 'pos/invoice_list.html', {
        'invoices': Paginator(invoices, DISPATCH_PER_PAGE).get_page(request.GET.get('page')),
        'pager': {'param': 'page', 'query': _query(request, ('page',)).urlencode()},
    })


@login_required
def invoice_detail(request, pk):
    invoice = get_visible_invoice(request.user, pk=pk)
    return render(request, 'pos/invoice_detail.html', {'invoice': invoice})


@login_required
def api_products_all(request):
    """Return all products as JSON for the POS."""
    products = list(with_stock(Product.objects.filter(is_active=True)).values(
        'id', 'sku', 'name', 'unit_price', 'unit', 'category__name', 'barcode', 'stock'
    ))
    return JsonResponse({'products': products})


# ── WMS: PALLETS ──────────────────────────────────────────────────────────────

def _gen_grn_number():
    """Auto-generate GRN number: GRN-YYYYMMDD-NNNN (sequential per day)."""
    today_str = timezone.now().strftime('%Y%m%d')
    prefix = f"GRN-{today_str}-"
    count = GoodsReceivedNote.objects.filter(grn_number__startswith=prefix).count()
    candidate = f"{prefix}{count + 1:04d}"
    while GoodsReceivedNote.objects.filter(grn_number=candidate).exists():
        count += 1
        candidate = f"{prefix}{count:04d}"
    return candidate


def _gen_batch_number():
    """Auto-generate batch number: BTH-YYYYMMDD-NNNN (sequential per day)."""
    today_str = timezone.now().strftime('%Y%m%d')
    prefix = f"BTH-{today_str}-"
    count = GRNItem.objects.filter(batch_number__startswith=prefix).count()
    candidate = f"{prefix}{count + 1:04d}"
    while GRNItem.objects.filter(batch_number=candidate).exists():
        count += 1
        candidate = f"{prefix}{count:04d}"
    return candidate


def _gen_lot():
    """Generate a unique lot number like LOT-20260705-A3B1."""
    ts = timezone.now().strftime('%Y%m%d')
    suffix = str(uuid.uuid4())[:4].upper()
    candidate = f"LOT-{ts}-{suffix}"
    while Pallet.objects.filter(lot_number=candidate).exists():
        candidate = f"LOT-{ts}-{str(uuid.uuid4())[:4].upper()}"
    return candidate


# ── WMS OPERATOR DASHBOARD ───────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def wms_dashboard(request):
    total_pallets = Pallet.objects.count()
    assigned_ids = PalletLocation.objects.filter(is_current=True).values_list('pallet_id', flat=True)
    unassigned_count = Pallet.objects.exclude(pk__in=assigned_ids).count()
    recent_grns = GoodsReceivedNote.objects.select_related('supplier').order_by('-received_at')[:4]
    recent_checkins = PalletLocation.objects.filter(is_current=True).select_related(
        'pallet__product', 'shelf', 'assigned_by'
    ).order_by('-assigned_at')[:4]
    return render(request, 'wms/wms_dashboard.html', {
        'total_pallets': total_pallets,
        'unassigned_count': unassigned_count,
        'containers_awaiting': Container.objects.filter(status=Container.STATUS_AT_WHARF).count(),
        'containers_open': Container.objects.filter(
            status__in=[Container.STATUS_CHECKED_IN, Container.STATUS_OPENED,
                        Container.STATUS_PALLETIZED]).count(),
        'recent_grns': recent_grns,
        'recent_checkins': recent_checkins,
        'today': timezone.localdate(),
    })


@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def pallet_list(request):
    q = request.GET.get('q', '').strip()
    location = request.GET.get('location', '')
    pallets = Pallet.objects.select_related('product', 'created_by').order_by('-created_at')
    shelved = PalletLocation.objects.filter(is_current=True).values('pallet')
    if location == 'unshelved':
        pallets = pallets.exclude(pk__in=shelved)
    elif location == 'shelved':
        pallets = pallets.filter(pk__in=shelved)
    else:
        location = ''
    if q:
        pallets = pallets.filter(
            Q(lot_number__icontains=q) |
            Q(product__name__icontains=q) |
            Q(product__sku__icontains=q)
        )
    # annotate current location
    pallet_data = []
    for p in pallets:
        pallet_data.append({'pallet': p, 'location': p.current_location})
    return render(request, 'wms/pallet_list.html', {'pallet_data': pallet_data, 'q': q, 'location': location,
                                                    'today': timezone.localdate()})


@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def pallet_create(request):
    grn_pk = request.GET.get('grn')
    grn = get_object_or_404(GoodsReceivedNote, pk=grn_pk) if grn_pk else None
    form = PalletForm(request.POST or None, grn=grn)
    if form.is_valid():
        pallet = form.save(commit=False)
        pallet.lot_number = _gen_lot()
        pallet.created_by = request.user
        pallet.save()
        messages.success(request, f'Pallet {pallet.lot_number} created. Print label and check it in to a shelf.')
        return redirect('pallet_label', pk=pallet.pk)
    return render(request, 'wms/pallet_create.html', {'form': form, 'grn': grn})


@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def pallet_label(request, pk):
    pallet = get_object_or_404(Pallet, pk=pk)
    return render(request, 'wms/pallet_label.html', {'pallet': pallet})


@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def pallet_edit(request, lot_number):
    pallet = get_object_or_404(Pallet, lot_number=lot_number)
    form = PalletEditForm(request.POST or None, instance=pallet)
    if form.is_valid():
        form.save()
        messages.success(request, f'Pallet {pallet.lot_number} updated.')
        return redirect('pallet_label', pk=pallet.pk)
    return render(request, 'wms/pallet_edit.html', {'pallet': pallet, 'form': form})


# ── WMS: SHELVES ──────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def shelf_list(request):
    shelves = ShelfLocation.objects.all()
    shelf_data = []
    for shelf in shelves:
        pallets = list(Pallet.objects.filter(
            location_history__shelf=shelf,
            location_history__is_current=True,
        ).select_related('product'))
        shelf_data.append({'shelf': shelf, 'pallets': pallets, 'count': len(pallets)})

    # Group by letter for the template
    from collections import OrderedDict
    shelf_by_letter = OrderedDict()
    for row in shelf_data:
        letter = row['shelf'].letter
        shelf_by_letter.setdefault(letter, []).append(row)

    return render(request, 'wms/shelf_list.html', {'shelf_data': shelf_data, 'shelf_by_letter': shelf_by_letter,
                                                   'add_form': ShelfAddForm(),
                                                   'is_admin': _user_role(request.user) == 'admin'})


@login_required
@role_required('admin')
def shelf_add(request):
    """Admin adds a row of shelves (or more levels to a row); QR codes follow from the codes."""
    if request.method != 'POST':
        return redirect('shelf_list')
    form = ShelfAddForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            messages.error(request, ' '.join(errors))
        return redirect('shelf_list')
    row, levels = form.cleaned_data['row'], form.cleaned_data['levels']
    created = [code for code in (f'{row}{n}' for n in range(1, levels + 1))
               if ShelfLocation.objects.get_or_create(
                   code=code, defaults={'letter': row, 'story': int(code[len(row):])})[1]]
    if created:
        messages.success(request, f"Added {', '.join(created)}. Print their QR codes from Row {row}.")
    else:
        messages.info(request, f'Row {row} already has levels 1–{levels} — nothing added.')
    return redirect(f"{reverse('shelf_list')}#row-{row}")


@login_required
@role_required('admin')
def shelf_edit(request, shelf_code):
    """Admin renames a shelf location, or deletes one that has never held a pallet."""
    shelf = get_object_or_404(ShelfLocation, code=shelf_code.upper())
    # Deleting would cascade away pallet location history, so only never-used shelves can go.
    used = shelf.pallet_assignments.exists()

    if request.method == 'POST' and 'delete' in request.POST:
        if used:
            messages.error(request, f'Shelf {shelf.code} has held pallets, so it cannot be deleted — rename it instead.')
            return redirect('shelf_edit', shelf_code=shelf.code)
        shelf.delete()
        messages.success(request, f'Shelf {shelf.code} deleted. Remove its QR label from the racking.')
        return redirect(f"{reverse('shelf_list')}#row-{shelf.letter}")

    form = ShelfEditForm(request.POST or None, shelf=shelf,
                         initial={'row': shelf.letter, 'level': shelf.story})
    if request.method == 'POST' and form.is_valid():
        old = shelf.code
        shelf.code, shelf.letter, shelf.story = (form.cleaned_data['code'], form.cleaned_data['row'],
                                                 form.cleaned_data['level'])
        shelf.save()
        if shelf.code != old:
            messages.success(request, f'Shelf {old} is now {shelf.code}. Reprint its QR label — the old one '
                                      f'still points to {old}.')
        return redirect(f"{reverse('shelf_list')}#row-{shelf.letter}")

    return render(request, 'wms/shelf_edit.html', {
        'shelf': shelf, 'form': form, 'used': used,
        'pallets': Pallet.objects.filter(location_history__shelf=shelf, location_history__is_current=True)
                                 .select_related('product'),
    })


@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def shelf_qr_print(request):
    shelves = ShelfLocation.objects.all()
    # ?row=AA prints just that row — handy after adding new shelves.
    row = request.GET.get('row', '').upper()
    if row:
        shelves = shelves.filter(letter=row)
    base_url = settings.QR_BASE_URL or f'{request.scheme}://{request.get_host()}'
    return render(request, 'wms/shelf_qr_print.html', {'shelves': shelves, 'base_url': base_url})


# ── WMS: CHECK-IN ─────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def wms_checkin(request, shelf_code=None):
    shelf = None
    if shelf_code:
        shelf = get_object_or_404(ShelfLocation, code=shelf_code.upper())

    form = CheckInForm(request.POST or None, initial={'shelf': shelf} if shelf else {})
    if shelf:
        form.fields['shelf'].initial = shelf

    if form.is_valid():
        lot = form.cleaned_data['lot_number'].strip()
        dest_shelf = form.cleaned_data['shelf']
        notes = form.cleaned_data.get('notes', '')
        try:
            pallet = Pallet.objects.get(lot_number=lot)
        except Pallet.DoesNotExist:
            form.add_error('lot_number', f'No pallet found with lot number "{lot}".')
        else:
            with transaction.atomic():
                # Mark any current assignment as no longer current
                PalletLocation.objects.filter(pallet=pallet, is_current=True).update(is_current=False)
                PalletLocation.objects.create(
                    pallet=pallet,
                    shelf=dest_shelf,
                    assigned_by=request.user,
                    is_current=True,
                    notes=notes,
                )
            messages.success(request, f'Pallet {pallet.lot_number} checked in to shelf {dest_shelf.code}.')
            return redirect('wms_checkin_shelf', shelf_code=dest_shelf.code)

    # Current pallets on the shelf
    current_pallets = []
    if shelf:
        current_pallets = Pallet.objects.filter(
            location_history__shelf=shelf,
            location_history__is_current=True,
        ).select_related('product')

    return render(request, 'wms/checkin.html', {
        'form': form,
        'shelf': shelf,
        'current_pallets': current_pallets,
        'shelves': ShelfLocation.objects.all(),
    })


# ── WMS: TRANSFER ─────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def wms_transfer(request):
    form = TransferForm(request.POST or None)
    pallet = None
    if request.method == 'POST' and form.is_valid():
        lot = form.cleaned_data['lot_number'].strip()
        to_shelf = form.cleaned_data['to_shelf']
        notes = form.cleaned_data.get('notes', '')
        try:
            pallet = Pallet.objects.get(lot_number=lot)
        except Pallet.DoesNotExist:
            form.add_error('lot_number', f'No pallet found with lot number "{lot}".')
        else:
            from_shelf = pallet.current_location
            with transaction.atomic():
                PalletLocation.objects.filter(pallet=pallet, is_current=True).update(is_current=False)
                PalletLocation.objects.create(
                    pallet=pallet,
                    shelf=to_shelf,
                    assigned_by=request.user,
                    is_current=True,
                    notes=f"Transferred from {from_shelf.code if from_shelf else 'unassigned'}: {notes}",
                )
            messages.success(request, f'Pallet {pallet.lot_number} transferred to shelf {to_shelf.code}.')
            return redirect('wms_transfer')

    elif request.method == 'GET' and request.GET.get('lot'):
        lot = request.GET.get('lot', '').strip()
        try:
            pallet = Pallet.objects.get(lot_number=lot)
        except Pallet.DoesNotExist:
            pallet = None

    return render(request, 'wms/transfer.html', {'form': form, 'pallet': pallet})


# ── WMS: PICKING TICKET ───────────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator', 'wms_dispatcher')
def picking_ticket(request, invoice_pk):
    invoice = get_visible_invoice(request.user, pk=invoice_pk)
    items = invoice.items.select_related('product').all()

    # For each item build a pick line with FEFO (earliest expiry first) pallets
    ticket_lines = []
    for item in items:
        shelf_locations = (
            ShelfLocation.objects
            .filter(
                pallet_assignments__pallet__product=item.product,
                pallet_assignments__is_current=True,
            )
            .distinct()
            .order_by('letter', 'story')
        )
        # Pallets on shelf for this product, sorted FEFO: dated pallets first (asc), undated last
        pallets_on_shelf = (
            Pallet.objects
            .filter(
                product=item.product,
                location_history__is_current=True,
            )
            .prefetch_related('location_history__shelf')
            .distinct()
        )
        pallets_sorted = sorted(
            pallets_on_shelf,
            key=lambda p: (p.expiry_date is None, p.expiry_date or date.max)
        )
        shelf_list = list(shelf_locations)
        ticket_lines.append({
            'item': item,
            'shelf_locations': shelf_list,
            'pallets': pallets_sorted,
        })

    # Sort lines: items with shelf assignments first, then A → Z by shelf letter
    ticket_lines.sort(key=lambda x: (
        0 if x['shelf_locations'] else 1,
        x['shelf_locations'][0].letter if x['shelf_locations'] else 'ZZ',
        x['shelf_locations'][0].story if x['shelf_locations'] else 99,
    ))

    return render(request, 'wms/picking_ticket.html', {
        'invoice': invoice,
        'ticket_lines': ticket_lines,
        'generated_by': request.user,
        'generated_at': timezone.now(),
    })


# ── WMS: MANAGER DASHBOARD ────────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager')
def manager_dashboard(request):
    from datetime import date as dt_date, timedelta as dt_td

    today = timezone.localdate()
    soon = today + dt_td(days=30)

    total_pallets = Pallet.objects.count()
    assigned_pallets = PalletLocation.objects.filter(is_current=True).values('pallet').distinct().count()
    unassigned_pallets = total_pallets - assigned_pallets

    total_shelves = ShelfLocation.objects.count()
    occupied_shelves = (
        ShelfLocation.objects
        .filter(pallet_assignments__is_current=True)
        .distinct()
        .count()
    )
    free_shelves = total_shelves - occupied_shelves

    products = with_stock(Product.objects.filter(is_active=True)).order_by('name')
    low_stock = products.filter(stock__lte=F('reorder_level'))
    out_of_stock = products.filter(stock__lte=0)

    expiring_pallets = Pallet.objects.filter(
        expiry_date__lte=soon,
        expiry_date__gte=today,
    ).select_related('product').order_by('expiry_date')

    expired_pallets = Pallet.objects.filter(
        expiry_date__lt=today,
    ).select_related('product').count()

    open_alerts = StockAlert.objects.filter(is_resolved=False).select_related('product').order_by('-created_at')[:20]

    recent_checkins = PalletLocation.objects.select_related(
        'pallet__product', 'shelf', 'assigned_by'
    ).order_by('-assigned_at')[:10]

    recent_dispatches = visible_invoices(request.user).filter(dispatch_status='dispatched').order_by('-dispatched_at')[:8]

    # All pallets with locations for the full stock view
    all_pallets = Pallet.objects.select_related('product', 'created_by').order_by('product__name', '-created_at')
    shelf_by_pallet = {loc.pallet_id: loc.shelf for loc in
                       PalletLocation.objects.filter(is_current=True).select_related('shelf')}
    pallet_stock = [{'pallet': p, 'location': shelf_by_pallet.get(p.pk)} for p in all_pallets]

    context = {
        'total_pallets': total_pallets,
        'assigned_pallets': assigned_pallets,
        'unassigned_pallets': unassigned_pallets,
        'total_shelves': total_shelves,
        'occupied_shelves': occupied_shelves,
        'free_shelves': free_shelves,
        'low_stock': low_stock,
        'low_stock_count': low_stock.count(),
        'out_of_stock': out_of_stock,
        'out_of_stock_count': out_of_stock.count(),
        'expiring_pallets': expiring_pallets,
        'expiring_count': expiring_pallets.count(),
        'expired_pallets': expired_pallets,
        'open_alerts': open_alerts,
        'open_alerts_count': open_alerts.count(),
        'recent_checkins': recent_checkins,
        'recent_dispatches': recent_dispatches,
        'pallet_stock': pallet_stock,
        'today': today,
    }
    return render(request, 'wms/manager_dashboard.html', context)


# ── WMS: API ──────────────────────────────────────────────────────────────────

@login_required
def api_pallet_lookup(request, lot_number):
    try:
        pallet = Pallet.objects.select_related('product').get(lot_number=lot_number)
        location = pallet.current_location
        return JsonResponse({
            'lot_number': pallet.lot_number,
            'product': pallet.product.name,
            'quantity': pallet.quantity,
            'expiry_date': str(pallet.expiry_date) if pallet.expiry_date else None,
            'current_shelf': location.code if location else None,
        })
    except Pallet.DoesNotExist:
        return JsonResponse({'error': 'Pallet not found'}, status=404)


# ── WMS DISPATCHER DASHBOARD ─────────────────────────────────────────────────

@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_dispatcher')
def wms_dispatcher_dashboard(request):
    pending_count = visible_invoices(request.user).filter(dispatch_status='pending').count()
    return render(request, 'wms/dispatcher_dashboard.html', {
        'pending_count': pending_count,
        'today': timezone.localdate(),
    })


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def dispatcher_add_comment(request, pk):
    """Add a comment/note to a dispatch order."""
    invoice = get_visible_invoice(request.user, pk=pk)
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            DispatchComment.objects.create(invoice=invoice, author=request.user, body=body)
            messages.success(request, 'Comment added.')
        else:
            messages.warning(request, 'Comment cannot be empty.')
    return redirect('warehouse_dispatch_detail', pk=pk)


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def dispatcher_edit_order(request, pk):
    """Allow dispatcher to adjust item quantities for a pending dispatch order."""
    invoice = get_visible_invoice(request.user, pk=pk, dispatch_status='pending')

    if request.method == 'POST':
        edit_reason = request.POST.get('edit_reason', '').strip()
        if not edit_reason:
            messages.error(request, 'A reason is required when editing order items.')
            return render(request, 'warehouse/edit_order.html', {
                'invoice': invoice,
                'item_data': _edit_order_rows(invoice),
            })

        with transaction.atomic():
            changes = []
            for item in invoice.items.all():
                qty_str = request.POST.get(f'qty_{item.pk}', '').strip()
                action = request.POST.get(f'action_{item.pk}', '')
                if action == 'delete':
                    changes.append(f'\u2022 Removed: {item.product.name} (was {item.quantity} {item.product.unit})')
                    item.delete()
                elif qty_str:
                    try:
                        new_qty = int(qty_str)
                        if new_qty > 0:
                            if new_qty != item.quantity:
                                changes.append(
                                    f'\u2022 {item.product.name}: {item.quantity} \u2192 {new_qty} {item.product.unit}'
                                )
                            item.quantity = new_qty
                            item.save(update_fields=['quantity'])
                        else:
                            changes.append(f'\u2022 Removed: {item.product.name} (qty set to 0)')
                            item.delete()
                    except (ValueError, TypeError):
                        pass
            invoice.calculate_total()

            # Save reason + change summary as a comment
            comment_lines = [f'\u270f\ufe0f Order edited by {request.user.get_full_name() or request.user.username}.']
            if changes:
                comment_lines.append('Changes:')
                comment_lines.extend(changes)
            comment_lines.append(f'Reason: {edit_reason}')
            DispatchComment.objects.create(
                invoice=invoice,
                author=request.user,
                body='\n'.join(comment_lines),
            )

        messages.success(request, f'Order {invoice.invoice_number} updated successfully.')
        return redirect('warehouse_dispatch_detail', pk=pk)

    return render(request, 'warehouse/edit_order.html', {
        'invoice': invoice,
        'item_data': _edit_order_rows(invoice),
    })


def _edit_order_rows(invoice):
    items = list(invoice.items.select_related('product').all())
    stock_map = stock_by_product([i.product_id for i in items])
    return [{'item': i, 'current_stock': stock_map[i.product_id]} for i in items]


# ── CONTAINERS ────────────────────────────────────────────────────────────────
#
# Flow:  broker lodges manifest at the wharf  →  warehouse checks the container
# in at HQ  →  warehouse opens it (raises the GRN, stock goes on hand)  →
# warehouse palletizes each manifest line  →  comments/damage reports  →  close.

# The customs broker now works in the CMS (cms_views.py); manifests are lodged from the warehouse side.
BROKER_ROLES = ('admin', 'manager', 'warehouse')
CONTAINERS_PER_PAGE = 20


def hq_cms_containers():
    """CMS boxes at the HQ yard that the warehouse unloads — not Ah Liki's own, not yet emptied."""
    return (CmsContainer.objects.filter(yard__code=Yard.HQ, returned=False)
            .exclude(owner__name=ShippingLine.AH_LIKI).exclude(status=CmsContainer.STATUS_EMPTY))
CONTAINER_WAREHOUSE_ROLES = ('admin', 'manager', 'warehouse', 'wms_operator')
CONTAINER_VIEW_ROLES = ('admin', 'manager', 'warehouse', 'wms_operator')


def _user_role(user):
    if user.is_superuser:
        return 'admin'
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.role


def _container_permissions(user, container):
    """Work out which actions this user may take on this container right now."""
    role = _user_role(user)
    is_warehouse = role in CONTAINER_WAREHOUSE_ROLES
    is_broker = role in BROKER_ROLES
    return {
        'can_edit': is_broker and container.is_editable,
        'can_check_in': is_warehouse and container.status == Container.STATUS_AT_WHARF,
        'can_open': is_warehouse and container.status == Container.STATUS_CHECKED_IN,
        'can_palletize': is_warehouse and container.status in (
            Container.STATUS_OPENED, Container.STATUS_PALLETIZED),
        # A box can be closed before everything is palletized and set aside; it is re-opened later.
        'can_close': is_warehouse and container.status in (Container.STATUS_OPENED, Container.STATUS_PALLETIZED),
        'can_reopen': is_warehouse and container.status == Container.STATUS_CLOSED and container.remaining_quantity > 0,
        'can_comment': (is_warehouse or is_broker) and container.status != Container.STATUS_CLOSED,
    }


@login_required
@role_required(*CONTAINER_VIEW_ROLES)
def container_list(request):
    """Customs broker view — every container they have lodged, by stage."""
    q = request.GET.get('q', '').strip()
    containers = Container.objects.select_related('supplier', 'container_type', 'created_by').prefetch_related('items')
    if q:
        containers = containers.filter(
            Q(container_number__icontains=q) |
            Q(vessel__icontains=q) |
            Q(container_type__name__icontains=q) |
            Q(supplier__name__icontains=q)
        )
    on_water = ShipmentTracking.objects.filter(show_in_my_containers=True, arrived_at__isnull=True) \
        .select_related('supplier').annotate(lodged=Count('containers')).filter(lodged=0)
    if q:
        on_water = on_water.filter(
            Q(request_number__icontains=q) |
            Q(vessel_name__icontains=q) |
            Q(container_numbers__icontains=q) |
            Q(supplier__name__icontains=q)
        )
    return render(request, 'containers/list.html', {
        'on_water': on_water,
        'at_wharf': containers.filter(status=Container.STATUS_AT_WHARF),
        'in_transit_to_hq': containers.filter(status=Container.STATUS_CHECKED_IN),
        'in_progress': containers.filter(status__in=[Container.STATUS_OPENED, Container.STATUS_PALLETIZED]),
        'closed': containers.filter(status=Container.STATUS_CLOSED),
        'q': q,
        'can_create': _user_role(request.user) in BROKER_ROLES,
        'today': timezone.localdate(),
    })


@login_required
@role_required(*BROKER_ROLES)
def container_create(request):
    """Customs broker lodges a container sitting at the wharf, with its manifest —
    or adds a new supplier (second tab) which is then pre-selected on the container.
    With ?cms=<id>, Inventory adds the list for a box already at the HQ yard instead."""
    cms = _cms_from_request(request)
    if cms and hasattr(cms, 'warehouse_container'):
        return redirect('container_edit', pk=cms.warehouse_container.pk)

    if request.method == 'POST' and 'add_supplier' in request.POST:
        supplier_form = SupplierForm(request.POST, prefix='sup')
        if supplier_form.is_valid():
            supplier = supplier_form.save()
            messages.success(request, f'Supplier {supplier.name} added — now lodge their container.')
            return redirect(f"{reverse('container_create')}?supplier={supplier.pk}"
                            + (f"&cms={cms.pk}" if cms else ''))
        return render(request, 'containers/form.html', _container_form_context(
            ContainerForm(initial=_container_initial(request), cms_container=cms), ContainerItemFormSet(), None,
            supplier_form=supplier_form, active_tab='supplier'))

    form = ContainerForm(request.POST or None, initial=_container_initial(request), cms_container=cms)
    formset = ContainerItemFormSet(request.POST or None)
    if request.method == 'POST':
        if form.is_valid() and formset.is_valid():
            items = [f for f in formset.forms
                     if f.cleaned_data and not f.cleaned_data.get('DELETE')
                     and f.cleaned_data.get('product')]
            if not items:
                messages.error(request, 'Add at least one item to the container manifest.')
            else:
                with transaction.atomic():
                    container = form.save(commit=False)
                    container.created_by = request.user
                    container.status = Container.STATUS_AT_WHARF
                    if cms:
                        # Already sitting at the HQ yard — ready to open as soon as the list is in.
                        container.cms_container = cms
                        container.status = Container.STATUS_CHECKED_IN
                        container.checked_in_by = request.user
                        container.checked_in_at = timezone.now()
                    container.save()
                    formset.instance = container
                    formset.save()
                    # The B/L has landed — take it off the water on the Atlas.
                    tracking = container.tracking
                    if tracking and not tracking.arrived_at:
                        tracking.arrived_at = timezone.now()
                        tracking.save(update_fields=['arrived_at'])
                where = 'added at HQ, ready to open,' if cms else 'lodged at the wharf'
                messages.success(
                    request,
                    f'Container {container.container_number} {where} with '
                    f'{container.items.count()} line(s).')
                return redirect('container_detail', pk=container.pk)
    return render(request, 'containers/form.html', _container_form_context(form, formset, None))


def _container_initial(request):
    """Pre-fill a new container from ?tracking=<id> (a tracked B/L) or ?supplier=<id>."""
    initial = {}
    tracking_id = request.GET.get('tracking', '')
    tracking = ShipmentTracking.objects.filter(pk=tracking_id).first() if tracking_id.isdigit() else None
    if tracking:
        initial.update(_tracking_autofill(tracking))
        initial['tracking'] = tracking.pk
    supplier_id = request.GET.get('supplier', '')
    if supplier_id.isdigit() and Supplier.objects.filter(pk=supplier_id).exists():
        initial['supplier'] = supplier_id
    cms = _cms_from_request(request)
    if cms:
        initial.update(container_number=cms.code, vessel=cms.vessel_voyage, arrival_date=cms.arrival_date,
                       notes=cms.description)
    initial.pop('container_numbers', None)
    return {k: v for k, v in initial.items() if v not in ('', None)}


def _cms_from_request(request):
    """The HQ-yard CMS box named by ?cms=<id>, if any."""
    cms_id = request.GET.get('cms', '')
    if not cms_id.isdigit():
        return None
    return hq_cms_containers().filter(pk=cms_id).first()


def _tracking_autofill(tracking):
    lodged = set(tracking.containers.values_list('container_number', flat=True))
    remaining = [n for n in tracking.container_number_list if n not in lodged]
    return {
        'container_number': remaining[0] if remaining else '',
        'container_numbers': remaining,
        'vessel': ' '.join(filter(None, [tracking.vessel_name, tracking.voyage_number])),
        'arrival_date': timezone.localtime(tracking.eta_at).date().isoformat() if tracking.eta_at else '',
        'supplier': tracking.supplier_id or '',
    }


def _container_form_context(form, formset, container, supplier_form=None, active_tab='container'):
    trackings = ShipmentTracking.objects.prefetch_related('containers')
    # Last container type / vessel per supplier, so picking a supplier fills the rest in.
    supplier_defaults = {}
    for c in Container.objects.filter(supplier__isnull=False).order_by('created_at'):
        supplier_defaults[c.supplier_id] = {'container_type': c.container_type_id or '', 'vessel': c.vessel}
    return {
        'form': form,
        'formset': formset,
        'container': container,
        'supplier_form': supplier_form or SupplierForm(prefix='sup'),
        'active_tab': active_tab,
        # Rendered inside <script>, so escape '<' to keep user text from closing the tag.
        'tracking_json': json.dumps({t.pk: _tracking_autofill(t) for t in trackings}).replace('<', '\\u003c'),
        'supplier_defaults_json': json.dumps(supplier_defaults).replace('<', '\\u003c'),
        'products_json': json.dumps(list(
            Product.objects.filter(is_active=True).values('id', 'name', 'sku').order_by('name')
        )),
    }


@login_required
@role_required(*BROKER_ROLES)
def container_edit(request, pk):
    """Amend a manifest — only while the container has not been opened."""
    container = get_object_or_404(Container, pk=pk)
    if not container.is_editable:
        messages.error(request, f'Container {container.container_number} has been opened and can no longer be edited.')
        return redirect('container_detail', pk=pk)

    form = ContainerForm(request.POST or None, instance=container)
    formset = ContainerItemFormSet(request.POST or None, instance=container)
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
        messages.success(request, f'Container {container.container_number} updated.')
        return redirect('container_detail', pk=pk)
    return render(request, 'containers/form.html', _container_form_context(form, formset, container))


@login_required
@role_required(*CONTAINER_VIEW_ROLES)
def container_detail(request, pk):
    container = get_object_or_404(
        Container.objects.select_related('supplier', 'container_type', 'created_by', 'checked_in_by',
                                         'opened_by', 'closed_by', 'grn'),
        pk=pk,
    )
    perms = _container_permissions(request.user, container)

    item_data = []
    for item in container.items.select_related('product').prefetch_related('pallets'):
        item_data.append({
            'item': item,
            'palletized': item.palletized_quantity,
            'remaining': item.remaining_quantity,
            'pallets': item.pallets.select_related('product').all(),
        })

    return render(request, 'containers/detail.html', {
        'container': container,
        'item_data': item_data,
        'comments': container.comments.select_related('author').all(),
        'comment_form': ContainerCommentForm(),
        'perms': perms,
        'damage_count': container.comments.filter(is_damage=True).count(),
    })


def _with_units_left(containers):
    """Annotate units_left: manifest units not yet built into pallets."""
    def total(qs):
        return Subquery(qs.values('container').annotate(t=Sum('quantity')).values('t')[:1])
    return containers.annotate(
        units_total=Coalesce(total(ContainerItem.objects.filter(container=OuterRef('pk'))), 0),
        units_palletized=Coalesce(Subquery(
            Pallet.objects.filter(container_item__container=OuterRef('pk')).values('container_item__container')
            .annotate(t=Sum('quantity')).values('t')[:1]), 0),
    ).annotate(units_left=Greatest(F('units_total') - F('units_palletized'), 0))


@login_required
@role_required(*CONTAINER_WAREHOUSE_ROLES)
def warehouse_container_list(request):
    """Warehouse 'Containers' tab — boxes at the HQ yard, then opening, palletizing and closing."""
    containers = Container.objects.select_related('supplier', 'container_type', 'created_by', 'checked_in_by') \
        .prefetch_related('items')
    # A box leaves 'At HQ' once it is opened; until then it waits for Inventory's list, then for opening.
    at_hq = hq_cms_containers().select_related('owner', 'warehouse_container') \
        .exclude(warehouse_container__status__in=[Container.STATUS_OPENED, Container.STATUS_PALLETIZED,
                                                  Container.STATUS_CLOSED]) \
        .annotate(lines=Count('warehouse_container__items')).order_by('arrival_date', 'code')
    owners = ShippingLine.objects.filter(pk__in=hq_cms_containers().values('owner'))
    q = request.GET.get('q', '').strip()
    owner = request.GET.get('owner', '')
    if q:
        at_hq = at_hq.filter(Q(code__icontains=q) | Q(description__icontains=q))
        containers = containers.filter(Q(container_number__icontains=q) | Q(notes__icontains=q)
                                       | Q(cms_container__description__icontains=q))
    if owner.isdigit():
        at_hq = at_hq.filter(owner_id=owner)
        containers = containers.filter(cms_container__owner_id=owner)
    tabs = {
        'at_hq': ('hq_page', at_hq),
        'open_containers': ('open_page', containers.filter(
            status__in=[Container.STATUS_OPENED, Container.STATUS_PALLETIZED])),
        # Boxes closed with products still inside come first, most left first; then the empty ones.
        'closed': ('closed_page', _with_units_left(containers.filter(status=Container.STATUS_CLOSED))
                   .order_by(Case(When(units_left__gt=0, then=Value(0)), default=Value(1)),
                             '-units_left', '-closed_at')),
    }
    context = {'can_add_list': _user_role(request.user) in BROKER_ROLES, 'today': timezone.localdate(),
               'owners': owners, 'q': q, 'selected_owner': owner}
    # Each tab pages on its own; its links keep the other tabs' pages.
    for name, (param, qs) in tabs.items():
        params = request.GET.copy()
        params.pop(param, None)
        context[name] = Paginator(qs, CONTAINERS_PER_PAGE).get_page(request.GET.get(param))
        context[f'{name}_pager'] = {'param': param, 'query': params.urlencode()}
    return render(request, 'warehouse/container_list.html', context)


@login_required
@role_required(*CONTAINER_WAREHOUSE_ROLES)
def container_check_in(request, pk):
    """Warehouse confirms the container has arrived at HQ from the wharf."""
    container = get_object_or_404(Container, pk=pk)
    if request.method != 'POST':
        return redirect('container_detail', pk=pk)
    if container.status != Container.STATUS_AT_WHARF:
        messages.warning(request, f'Container {container.container_number} has already been checked in.')
        return redirect('container_detail', pk=pk)

    container.status = Container.STATUS_CHECKED_IN
    container.checked_in_by = request.user
    container.checked_in_at = timezone.now()
    container.save(update_fields=['status', 'checked_in_by', 'checked_in_at'])
    messages.success(request, f'Container {container.container_number} checked in at HQ. Open it when you are ready to unload.')
    return redirect('container_detail', pk=pk)


@login_required
@role_required(*CONTAINER_WAREHOUSE_ROLES)
def container_open(request, pk):
    """Open the container: raise the GRN and bring the manifest on hand as stock."""
    container = get_object_or_404(Container, pk=pk)
    if request.method != 'POST':
        return redirect('container_detail', pk=pk)
    if container.status != Container.STATUS_CHECKED_IN:
        messages.warning(request, f'Container {container.container_number} cannot be opened from status "{container.get_status_display()}".')
        return redirect('container_detail', pk=pk)
    if not container.items.exists():
        messages.error(request, 'This container has no manifest lines — nothing to receive.')
        return redirect('container_detail', pk=pk)

    with transaction.atomic():
        grn = GoodsReceivedNote.objects.create(
            grn_number=_gen_grn_number(),
            supplier=container.supplier,
            received_by=request.user,
            received_at=timezone.now(),
            notes=f'Auto-generated on opening container {container.container_number}.',
        )
        for item in container.items.select_related('product'):
            grn_item = GRNItem.objects.create(
                grn=grn,
                product=item.product,
                quantity_received=item.quantity,
                batch_number=_gen_batch_number(),
                expiry_date=item.expiry_date,
                unit_cost=0,
            )
            item.grn_item = grn_item
            item.save(update_fields=['grn_item'])
            StockMovement.objects.create(
                product=item.product,
                movement_type='in',
                quantity=item.quantity,
                reference=grn.grn_number,
                batch_number=grn_item.batch_number,
                expiry_date=item.expiry_date,
                performed_by=request.user,
                notes=f'Container {container.container_number}',
            )
            check_and_create_alerts(item.product)

        container.grn = grn
        container.status = Container.STATUS_OPENED
        container.opened_by = request.user
        container.opened_at = timezone.now()
        container.save(update_fields=['grn', 'status', 'opened_by', 'opened_at'])

    messages.success(
        request,
        f'Container {container.container_number} opened. {grn.grn_number} raised and stock updated — '
        f'now palletize the items.')
    return redirect('container_detail', pk=pk)


@login_required
@role_required(*CONTAINER_WAREHOUSE_ROLES)
def container_palletize(request, pk, item_pk):
    """Build a pallet from one manifest line of an opened container."""
    container = get_object_or_404(Container, pk=pk)
    item = get_object_or_404(ContainerItem, pk=item_pk, container=container)

    if container.status not in (Container.STATUS_OPENED, Container.STATUS_PALLETIZED):
        messages.error(request, 'Open the container before palletizing its contents.')
        return redirect('container_detail', pk=pk)
    if item.remaining_quantity <= 0:
        messages.warning(request, f'{item.product.name} is already fully palletized.')
        return redirect('container_detail', pk=pk)

    initial = {'quantity': item.remaining_quantity, 'expiry_date': item.expiry_date}
    form = ContainerPalletForm(request.POST or None, container_item=item, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            pallet = Pallet.objects.create(
                lot_number=_gen_lot(),
                product=item.product,
                grn_item=item.grn_item,
                container_item=item,
                quantity=form.cleaned_data['quantity'],
                expiry_date=form.cleaned_data.get('expiry_date') or item.expiry_date,
                created_by=request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
            container.refresh_palletized_status()
        messages.success(
            request,
            f'Pallet {pallet.lot_number} built from container {container.container_number}. '
            f'Print the label and check it in to a shelf.')
        return redirect('pallet_label', pk=pallet.pk)

    return render(request, 'containers/palletize.html', {
        'container': container,
        'item': item,
        'form': form,
    })


@login_required
@role_required(*CONTAINER_WAREHOUSE_ROLES)
def container_close(request, pk):
    """Close the container. Anything not yet palletized stays inside, set aside to re-open later."""
    container = get_object_or_404(Container, pk=pk)
    if request.method != 'POST':
        return redirect('container_detail', pk=pk)

    container.refresh_palletized_status()
    if container.status == Container.STATUS_CLOSED:
        messages.warning(request, f'Container {container.container_number} is already closed.')
        return redirect('container_detail', pk=pk)
    if container.status not in (Container.STATUS_OPENED, Container.STATUS_PALLETIZED):
        messages.error(request, f'Open container {container.container_number} before closing it.')
        return redirect('container_detail', pk=pk)

    # A closing note is optional, but capture it as a comment when supplied.
    body = request.POST.get('closing_comment', '').strip()
    if body:
        ContainerComment.objects.create(
            container=container,
            author=request.user,
            body=body,
            is_damage=bool(request.POST.get('closing_is_damage')),
        )

    left = container.remaining_quantity
    with transaction.atomic():
        container.status = Container.STATUS_CLOSED
        container.closed_by = request.user
        container.closed_at = timezone.now()
        container.save(update_fields=['status', 'closed_by', 'closed_at'])
        # Unloaded — the broker now sees the box as Empty, ready to go back.
        # With products still inside it stays as it is until it is re-opened and emptied.
        if container.cms_container and not left:
            cms = container.cms_container
            was = cms.get_status_display()
            cms.status = CmsContainer.STATUS_EMPTY
            cms.save()
            if was != cms.get_status_display():
                cms_audit.record(request, 'status_changed', f'{cms.code} set to Empty when the warehouse closed it',
                                 cms, cms.code, {'Status': [was, cms.get_status_display()]},
                                 f'Warehouse: {container.container_number}')
    if left:
        messages.success(request, f'Container {container.container_number} closed with {left} unit{pluralize(left)} '
                                  f'still inside. Re-open it from the Closed tab to finish palletizing.')
    else:
        messages.success(request, f'Container {container.container_number} closed.')
    return redirect('container_detail', pk=pk)


@login_required
@role_required(*CONTAINER_WAREHOUSE_ROLES)
def container_reopen(request, pk):
    """Re-open a container that was closed with products still inside, to palletize the rest."""
    container = get_object_or_404(Container, pk=pk)
    if request.method != 'POST':
        return redirect('container_detail', pk=pk)
    if container.status != Container.STATUS_CLOSED or container.remaining_quantity <= 0:
        messages.warning(request, f'Container {container.container_number} has nothing left to palletize.')
        return redirect('container_detail', pk=pk)

    container.status = Container.STATUS_OPENED
    container.closed_by = None
    container.closed_at = None
    container.save(update_fields=['status', 'closed_by', 'closed_at'])
    messages.success(request, f'Container {container.container_number} re-opened — '
                              f'{container.remaining_quantity} unit{pluralize(container.remaining_quantity)} to palletize.')
    return redirect('container_detail', pk=pk)


@login_required
@role_required(*CONTAINER_VIEW_ROLES)
def container_add_comment(request, pk):
    """Standalone comment endpoint (damage/breakage reports)."""
    container = get_object_or_404(Container, pk=pk)
    if request.method == 'POST':
        if container.status == Container.STATUS_CLOSED:
            messages.error(request, 'This container is closed — no further comments can be added.')
        else:
            form = ContainerCommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.container = container
                comment.author = request.user
                comment.save()
                messages.success(request, 'Comment added to the container.')
            else:
                messages.warning(request, 'Comment cannot be empty.')
    return redirect('container_detail', pk=pk)


# ── TRACK CONTAINERS + AH LIKI ATLAS (Customs Broker) ─────────────────────────

def _flash_sync(request, tracking, ok, message):
    (messages.success if ok else messages.warning)(request, f'{tracking.request_number}: {message}')


def _safe_next(request, default='track_list'):
    nxt = request.POST.get('next', '')
    return nxt if nxt.startswith('/') and not nxt.startswith('//') else default


@login_required
@role_required(*BROKER_ROLES)
def track_list(request):
    """Enter a bill of lading to track with Terminal49 and follow it to Apia."""
    form = ShipmentTrackingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        tracking = form.save(commit=False)
        tracking.created_by = request.user
        tracking.save()
        ok, message = terminal49.sync_tracking(tracking)
        if tracking.t49_status == 'failed':
            # Terminal49 says the number is not a real shipment — don't keep it.
            tracking.delete()
            form.add_error('request_number', f'Terminal49 could not find this number: '
                                             f'{tracking.t49_failed_reason or message}')
        else:
            _flash_sync(request, tracking, ok, message)
            return redirect('track_list')

    trackings = ShipmentTracking.objects.select_related('supplier', 'created_by') \
        .annotate(lodged=Count('containers'))
    return render(request, 'containers/track.html', {
        'form': form,
        'tracking': None,
        'on_water': [t for t in trackings if not t.arrived_at and not t.lodged],
        'arrived': [t for t in trackings if t.arrived_at or t.lodged],
        'port_choices': terminal49.port_choices(),
        't49_configured': terminal49.is_configured(),
        'auto_refresh_hours': auto_refresh.refresh_hours(),
    })


@login_required
@role_required(*BROKER_ROLES)
def track_edit(request, pk):
    tracking = get_object_or_404(ShipmentTracking, pk=pk)
    number_before = tracking.request_number
    form = ShipmentTrackingForm(request.POST or None, instance=tracking)
    if request.method == 'POST' and form.is_valid():
        tracking = form.save(commit=False)
        if tracking.request_number != number_before:
            # A different number is a different Terminal49 tracking request.
            tracking.t49_request_id = tracking.t49_shipment_id = tracking.route_geojson = ''
            tracking.t49_status = 'not_sent'
            tracking.latitude = tracking.longitude = None
        tracking.save()
        if not tracking.t49_request_id:
            _flash_sync(request, tracking, *terminal49.sync_tracking(tracking))
        else:
            messages.success(request, f'{tracking.request_number} updated.')
        return redirect('track_list')
    return render(request, 'containers/track.html', {
        'form': form,
        'tracking': tracking,
        'port_choices': terminal49.port_choices(),
        't49_configured': terminal49.is_configured(),
        'auto_refresh_hours': auto_refresh.refresh_hours(),
    })


@login_required
@role_required(*BROKER_ROLES)
def track_refresh(request, pk=None):
    """Re-sync one tracked B/L (or every one still on the water) with Terminal49."""
    if request.method != 'POST':
        return redirect('track_list')
    if pk:
        tracking = get_object_or_404(ShipmentTracking, pk=pk)
        _flash_sync(request, tracking, *terminal49.sync_tracking(tracking))
    else:
        results = [terminal49.sync_tracking(t)
                   for t in ShipmentTracking.objects.filter(arrived_at__isnull=True)]
        failed = sum(1 for ok, _ in results if not ok)
        if failed:
            messages.warning(request, f'Refreshed {len(results)} shipment(s); {failed} could not be synced.')
        else:
            messages.success(request, f'Refreshed {len(results)} shipment(s) with Terminal49.')
    return redirect(_safe_next(request))


@login_required
@role_required(*BROKER_ROLES)
def track_toggle(request, pk):
    """Add / remove a tracked B/L from the My Containers page."""
    tracking = get_object_or_404(ShipmentTracking, pk=pk)
    if request.method == 'POST':
        tracking.show_in_my_containers = not tracking.show_in_my_containers
        tracking.save(update_fields=['show_in_my_containers'])
        verb = 'added to' if tracking.show_in_my_containers else 'removed from'
        messages.success(request, f'{tracking.request_number} {verb} My Containers.')
    return redirect(_safe_next(request))


@login_required
@role_required(*BROKER_ROLES)
def track_delete(request, pk):
    tracking = get_object_or_404(ShipmentTracking, pk=pk)
    if request.method == 'POST':
        number = tracking.request_number
        tracking.delete()
        messages.success(request, f'Stopped tracking {number}.')
    return redirect('track_list')


@login_required
@role_required(*CONTAINER_VIEW_ROLES)
def atlas(request):
    """Ah Liki Atlas — bird's-eye map of every ship bound for Samoa."""
    return render(request, 'containers/atlas.html', {
        'focus': request.GET.get('focus', ''),
        'can_track': _user_role(request.user) in BROKER_ROLES,
    })


@login_required
@role_required(*CONTAINER_VIEW_ROLES)
def atlas_data(request):
    include_arrived = request.GET.get('arrived') == '1'
    ships, unplaced = [], []
    for t in ShipmentTracking.objects.select_related('supplier').prefetch_related('containers'):
        if (t.arrived_at or t.lodged_count) and not include_arrived:
            continue
        v = terminal49.voyage(t)
        if v is None:
            unplaced.append({'id': t.pk, 'number': t.request_number,
                             'edit_url': reverse('track_edit', args=[t.pk])})
            continue
        v['edit_url'] = reverse('track_edit', args=[t.pk])
        v['lodge_url'] = f"{reverse('container_create')}?tracking={t.pk}"
        ships.append(v)
    ships.sort(key=lambda v: v['eta'] or '')
    return JsonResponse({
        'apia': terminal49.APIA,
        'ships': ships,
        'unplaced': unplaced,
        'generated_at': timezone.now().isoformat(),
    })
