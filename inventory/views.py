import csv
import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, Count, Min, Q, F, Case, When, Value, IntegerField, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from .models import (Product, Category, Supplier, GoodsReceivedNote, GRNItem,
                     StockMovement, Sale, SaleItem, StockAlert, PurchaseOrder, UserProfile,
                     Pallet, ShelfLocation, PalletLocation, DispatchComment,
                     Container, ContainerItem, ContainerComment, ShipmentTracking)
from .forms import (ProductForm, SupplierForm, CategoryForm, GRNForm, GRNItemFormSet,
                    SaleForm, SaleItemFormSet, StockAdjustForm,
                    PalletForm, CheckInForm, TransferForm, PalletEditForm,
                    ContainerForm, ContainerItemFormSet, ContainerCommentForm,
                    ContainerPalletForm, ShipmentTrackingForm)
from . import auto_refresh, terminal49


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
    soon = date.today() + timedelta(days=30)
    expiring = GRNItem.objects.filter(product=product, expiry_date__lte=soon, expiry_date__gte=date.today())
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
    products = with_stock(Product.objects.filter(is_active=True)).order_by('name')
    low_stock = products.filter(stock__lte=F('reorder_level'))
    out_of_stock = products.filter(stock__lte=0)
    total_products = products.count()
    low_stock_count = low_stock.count()
    out_of_stock_count = out_of_stock.count()
    recent_sales = Sale.objects.order_by('-created_at')[:5]
    recent_grns = GoodsReceivedNote.objects.order_by('-received_at')[:5]
    open_alerts = StockAlert.objects.filter(is_resolved=False).order_by('-created_at')[:10]

    today = date.today()
    sales_today = Sale.objects.filter(created_at__date=today)
    sales_today_total = sales_today.aggregate(t=Sum('total_amount'))['t'] or 0

    # Sales last 7 days for chart
    sales_chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        amt = Sale.objects.filter(created_at__date=d).aggregate(t=Sum('total_amount'))['t'] or 0
        sales_chart.append({'date': d.strftime('%d %b'), 'amount': float(amt)})

    # Stock value
    stock_value = total_stock_value()

    # Warehouse-specific
    pending_dispatch = Invoice.objects.filter(dispatch_status='pending').select_related('cashier').order_by('-created_at')[:8]
    pending_dispatch_count = Invoice.objects.filter(dispatch_status='pending').count()

    # Dispatch activity — last 7 days
    dispatch_chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = Invoice.objects.filter(dispatch_status='dispatched', dispatched_at__date=d).count()
        dispatch_chart.append({'date': d.strftime('%d %b'), 'count': count})

    # Stock health breakdown
    healthy_stock = total_products - low_stock_count
    low_not_zero = low_stock_count - out_of_stock_count

    context = {
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'low_stock_page': Paginator(low_stock, 20).get_page(request.GET.get('low_page')),
        'out_of_stock_page': Paginator(out_of_stock, 20).get_page(request.GET.get('out_page')),
        'out_of_stock_count': out_of_stock_count,
        'open_alerts_count': open_alerts.count(),
        'open_alerts': open_alerts,
        'recent_sales': recent_sales,
        'recent_grns': recent_grns,
        'sales_today_total': sales_today_total,
        'sales_today_count': sales_today.count(),
        'sales_chart_json': json.dumps(sales_chart),
        'stock_value': stock_value,
        'pending_dispatch': pending_dispatch,
        'pending_dispatch_count': pending_dispatch_count,
        'dispatch_chart_json': json.dumps(dispatch_chart),
        'healthy_stock': healthy_stock,
        'low_not_zero': low_not_zero,
    }
    return render(request, 'dashboard.html', context)


# ── PRODUCTS ──────────────────────────────────────────────────────────────────

@login_required
def product_list(request):
    q = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    products = Product.objects.select_related('category', 'supplier').filter(is_active=True)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
    if category_id:
        products = products.filter(category_id=category_id)
    categories = Category.objects.all()
    product_data = [{'product': p, 'stock': p.stock, 'low': p.stock <= p.reorder_level}
                    for p in with_stock(products)]
    return render(request, 'products/list.html', {'product_data': product_data, 'categories': categories, 'q': q, 'selected_cat': category_id})


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

    today = date.today()
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


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    movements = product.stock_movements.order_by('-timestamp')[:20]
    alerts = product.alerts.filter(is_resolved=False)
    return render(request, 'products/detail.html', {
        'product': product,
        'movements': movements,
        'alerts': alerts,
        'current_stock': product.current_stock,
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

@login_required
@role_required('admin', 'warehouse')
def stock_movements(request):
    movements = StockMovement.objects.select_related('product', 'performed_by').order_by('-timestamp')[:100]
    return render(request, 'stock/movements.html', {'movements': movements})


@login_required
@role_required('admin', 'warehouse')
def stock_adjust(request):
    form = StockAdjustForm(request.POST or None)
    if form.is_valid():
        movement = form.save(commit=False)
        movement.performed_by = request.user
        movement.save()
        check_and_create_alerts(movement.product)
        messages.success(request, 'Stock adjustment recorded.')
        return redirect('stock_movements')
    return render(request, 'stock/adjust.html', {'form': form})


# ── ALERTS ────────────────────────────────────────────────────────────────────

@login_required
def alert_list(request):
    alerts = StockAlert.objects.select_related('product').order_by('is_resolved', '-created_at')
    return render(request, 'alerts/list.html', {'alerts': alerts})


@login_required
@role_required('admin', 'warehouse')
def alert_resolve(request, pk):
    alert = get_object_or_404(StockAlert, pk=pk)
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.save()
    messages.success(request, 'Alert marked as resolved.')
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
        d = date.today().replace(day=1) - timedelta(days=i*30)
        amt = Sale.objects.filter(created_at__year=d.year, created_at__month=d.month).aggregate(t=Sum('total_amount'))['t'] or 0
        monthly.append({'month': d.strftime('%b %Y'), 'amount': float(amt)})

    low_stock = products.filter(stock__lte=F('reorder_level'))
    expiring_soon = GRNItem.objects.filter(
        expiry_date__lte=date.today() + timedelta(days=30),
        expiry_date__gte=date.today()
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
            UserProfile.objects.filter(user=u).update(role=role)
            messages.success(request, f'User "{username}" created successfully.')
            return redirect('user_list')
    return render(request, 'users/add.html')


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
        profile.save()
        new_pw = request.POST.get('new_password', '').strip()
        if new_pw:
            u.set_password(new_pw)
            u.save()
        messages.success(request, f'User "{u.username}" updated.')
        return redirect('user_list')
    return render(request, 'users/edit.html', {'u': u, 'profile': profile})


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
    if request.method == 'POST':
        form = InvoiceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            invoice = form.save(commit=False)
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
    return render(request, 'pos/invoice_upload.html', {'form': form})



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

@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def warehouse_dispatch_list(request):
    """List invoices pending dispatch and recently dispatched ones."""
    pending = Invoice.objects.filter(dispatch_status='pending').select_related('cashier').order_by('-created_at')
    dispatch_log = Invoice.objects.filter(dispatch_status='dispatched').select_related('cashier', 'dispatched_by').order_by('-dispatched_at')
    return render(request, 'warehouse/dispatch_list.html', {
        'pending': pending,
        'dispatch_log': dispatch_log,
    })


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def warehouse_dispatch_detail(request, pk):
    """Show the dispatch detail for a single invoice."""
    invoice = get_object_or_404(Invoice, pk=pk)

    # Handle inline comment submission
    if request.method == 'POST' and request.POST.get('add_comment'):
        body = request.POST.get('comment_body', '').strip()
        if body:
            DispatchComment.objects.create(invoice=invoice, author=request.user, body=body)
            messages.success(request, 'Comment added.')
        return redirect('warehouse_dispatch_detail', pk=pk)

    items = list(invoice.items.select_related('product').all())
    stock_map = stock_by_product([i.product_id for i in items])
    item_data = []
    for item in items:
        stock = stock_map[item.product_id]
        item_data.append({
            'item': item,
            'current_stock': stock,
            'sufficient': stock >= item.quantity,
            'default_dispatch_qty': min(item.quantity, stock) if stock > 0 else 0,
        })
    comments = invoice.comments.select_related('author').all()
    return render(request, 'warehouse/dispatch_detail.html', {
        'invoice': invoice,
        'item_data': item_data,
        'comments': comments,
    })


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def warehouse_dispatch_submit(request, pk):
    """Confirm dispatch — for PDF invoices just marks dispatched; for item invoices deducts stock."""
    invoice = get_object_or_404(Invoice, pk=pk)
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
            elif dqty > stock_map[item.product_id]:
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
    """Export the dispatch log as a CSV, with optional date/search filters."""
    from datetime import datetime
    qs = Invoice.objects.filter(dispatch_status='dispatched').select_related('cashier', 'dispatched_by').order_by('-dispatched_at')

    q     = request.GET.get('q', '').strip().lower()
    from_ = request.GET.get('from', '').strip()
    to_   = request.GET.get('to', '').strip()

    if from_:
        try:
            qs = qs.filter(dispatched_at__date__gte=datetime.strptime(from_, '%Y-%m-%d').date())
        except ValueError:
            pass
    if to_:
        try:
            qs = qs.filter(dispatched_at__date__lte=datetime.strptime(to_, '%Y-%m-%d').date())
        except ValueError:
            pass
    if q:
        qs = qs.filter(
            Q(invoice_number__icontains=q) |
            Q(customer_name__icontains=q) |
            Q(truck_plate__icontains=q) |
            Q(dispatched_by__first_name__icontains=q) |
            Q(dispatched_by__last_name__icontains=q) |
            Q(dispatched_by__username__icontains=q)
        )

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
def invoice_list(request):
    invoices = Invoice.objects.select_related('cashier').order_by('-created_at')
    return render(request, 'pos/invoice_list.html', {'invoices': invoices})


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    return render(request, 'pos/invoice_detail.html', {'invoice': invoice})


@login_required
def invoice_mark_paid(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice.status = 'paid'
        invoice.payment_method = request.POST.get('payment_method', 'cash')
        invoice.save()
        messages.success(request, f'Invoice {invoice.invoice_number} marked as paid.')
    return redirect('invoice_detail', pk=pk)


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
        'today': date.today(),
    })


@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def pallet_list(request):
    q = request.GET.get('q', '').strip()
    pallets = Pallet.objects.select_related('product', 'created_by').order_by('-created_at')
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
    return render(request, 'wms/pallet_list.html', {'pallet_data': pallet_data, 'q': q, 'today': date.today()})


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

    return render(request, 'wms/shelf_list.html', {'shelf_data': shelf_data, 'shelf_by_letter': shelf_by_letter})


@login_required
@role_required('admin', 'manager', 'warehouse', 'wms_operator')
def shelf_qr_print(request):
    shelves = ShelfLocation.objects.all()
    return render(request, 'wms/shelf_qr_print.html', {'shelves': shelves})


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
    from .models import Invoice
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
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

    today = dt_date.today()
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

    from .models import Invoice as Inv
    recent_dispatches = Inv.objects.filter(dispatch_status='dispatched').order_by('-dispatched_at')[:8]

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
    from .models import Invoice as Inv
    pending_count = Inv.objects.filter(dispatch_status='pending').count()
    return render(request, 'wms/dispatcher_dashboard.html', {
        'pending_count': pending_count,
        'today': date.today(),
    })


@login_required
@role_required('admin', 'warehouse', 'wms_dispatcher')
def dispatcher_add_comment(request, pk):
    """Add a comment/note to a dispatch order."""
    from .models import Invoice as Inv
    invoice = get_object_or_404(Inv, pk=pk)
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
    from .models import Invoice as Inv, InvoiceItem
    invoice = get_object_or_404(Inv, pk=pk, dispatch_status='pending')

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
        'can_close': is_warehouse and container.status == Container.STATUS_PALLETIZED,
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
        'today': date.today(),
    })


@login_required
@role_required(*BROKER_ROLES)
def container_create(request):
    """Customs broker lodges a container sitting at the wharf, with its manifest —
    or adds a new supplier (second tab) which is then pre-selected on the container."""
    if request.method == 'POST' and 'add_supplier' in request.POST:
        supplier_form = SupplierForm(request.POST, prefix='sup')
        if supplier_form.is_valid():
            supplier = supplier_form.save()
            messages.success(request, f'Supplier {supplier.name} added — now lodge their container.')
            return redirect(f"{reverse('container_create')}?supplier={supplier.pk}")
        return render(request, 'containers/form.html', _container_form_context(
            ContainerForm(initial=_container_initial(request)), ContainerItemFormSet(), None,
            supplier_form=supplier_form, active_tab='supplier'))

    form = ContainerForm(request.POST or None, initial=_container_initial(request))
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
                    container.save()
                    formset.instance = container
                    formset.save()
                    # The B/L has landed — take it off the water on the Atlas.
                    tracking = container.tracking
                    if tracking and not tracking.arrived_at:
                        tracking.arrived_at = timezone.now()
                        tracking.save(update_fields=['arrived_at'])
                messages.success(
                    request,
                    f'Container {container.container_number} lodged at the wharf with '
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
    initial.pop('container_numbers', None)
    return {k: v for k, v in initial.items() if v not in ('', None)}


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


@login_required
@role_required(*CONTAINER_WAREHOUSE_ROLES)
def warehouse_container_list(request):
    """Warehouse 'Containers' tab — check in containers arriving from the wharf."""
    containers = Container.objects.select_related('supplier', 'container_type', 'created_by', 'checked_in_by') \
        .prefetch_related('items')
    return render(request, 'warehouse/container_list.html', {
        'awaiting_checkin': containers.filter(status=Container.STATUS_AT_WHARF),
        'at_hq': containers.filter(status=Container.STATUS_CHECKED_IN),
        'open_containers': containers.filter(
            status__in=[Container.STATUS_OPENED, Container.STATUS_PALLETIZED]),
        'closed': containers.filter(status=Container.STATUS_CLOSED),
        'today': date.today(),
    })


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
    """Close the container once everything is out and palletized."""
    container = get_object_or_404(Container, pk=pk)
    if request.method != 'POST':
        return redirect('container_detail', pk=pk)

    container.refresh_palletized_status()
    if container.status == Container.STATUS_CLOSED:
        messages.warning(request, f'Container {container.container_number} is already closed.')
        return redirect('container_detail', pk=pk)
    if container.status != Container.STATUS_PALLETIZED:
        messages.error(
            request,
            f'Container {container.container_number} still has {container.remaining_quantity} '
            f'unit(s) to palletize before it can be closed.')
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

    container.status = Container.STATUS_CLOSED
    container.closed_by = request.user
    container.closed_at = timezone.now()
    container.save(update_fields=['status', 'closed_by', 'closed_at'])
    messages.success(request, f'Container {container.container_number} closed.')
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
