import csv
import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from .models import (Product, Category, Supplier, GoodsReceivedNote, GRNItem,
                     StockMovement, Sale, SaleItem, StockAlert, PurchaseOrder, UserProfile,
                     Pallet, ShelfLocation, PalletLocation, DispatchComment)
from .forms import (ProductForm, SupplierForm, CategoryForm, GRNForm, GRNItemFormSet,
                    SaleForm, SaleItemFormSet, StockAdjustForm,
                    PalletForm, CheckInForm, TransferForm, PalletEditForm)


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
            if profile.role == 'cashier':
                return redirect('pos')
            return redirect('pos')
        return _wrapped
    return decorator


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
    products = Product.objects.filter(is_active=True)
    low_stock = [p for p in products if p.is_low_stock]
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
    stock_value = sum(p.stock_value for p in products)

    # Warehouse-specific
    pending_dispatch = Invoice.objects.filter(dispatch_status='pending').select_related('cashier').order_by('-created_at')[:8]
    pending_dispatch_count = Invoice.objects.filter(dispatch_status='pending').count()
    out_of_stock = [p for p in products if p.current_stock <= 0]

    # Dispatch activity — last 7 days
    dispatch_chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = Invoice.objects.filter(dispatch_status='dispatched', dispatched_at__date=d).count()
        dispatch_chart.append({'date': d.strftime('%d %b'), 'count': count})

    # Stock health breakdown
    healthy_stock = products.count() - len(low_stock)
    low_not_zero = len(low_stock) - len(out_of_stock)

    context = {
        'total_products': products.count(),
        'low_stock_count': len(low_stock),
        'low_stock_products': low_stock,
        'out_of_stock': out_of_stock,
        'out_of_stock_count': len(out_of_stock),
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
    # Annotate with current stock
    product_data = []
    for p in products:
        product_data.append({'product': p, 'stock': p.current_stock, 'low': p.is_low_stock})
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
    products = Product.objects.filter(is_active=True)
    total_stock_value = sum(p.stock_value for p in products)
    top_sellers = SaleItem.objects.values('product__name').annotate(
        total_qty=Sum('quantity'), total_rev=Sum('unit_price')
    ).order_by('-total_qty')[:10]

    # Monthly sales last 6 months
    monthly = []
    for i in range(5, -1, -1):
        d = date.today().replace(day=1) - timedelta(days=i*30)
        amt = Sale.objects.filter(created_at__year=d.year, created_at__month=d.month).aggregate(t=Sum('total_amount'))['t'] or 0
        monthly.append({'month': d.strftime('%b %Y'), 'amount': float(amt)})

    low_stock = [p for p in products if p.is_low_stock]
    expiring_soon = GRNItem.objects.filter(
        expiry_date__lte=date.today() + timedelta(days=30),
        expiry_date__gte=date.today()
    ).select_related('product')

    context = {
        'total_stock_value': total_stock_value,
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
    for p in Product.objects.filter(is_active=True).select_related('category', 'supplier'):
        writer.writerow([p.sku, p.name, p.category or '', p.supplier or '', p.current_stock,
                         p.unit, p.reorder_level, p.cost_price, p.stock_value])
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


# ── POS (Cashier View) ─────────────────────────────────────────────────────────

from .models import Quote, QuoteItem, Invoice, InvoiceItem
from decimal import Decimal
import uuid

def gen_number(prefix):
    from django.utils import timezone
    ts = timezone.now().strftime('%Y%m%d%H%M%S')
    return f"{prefix}-{ts}-{str(uuid.uuid4())[:4].upper()}"


@login_required
@role_required('admin', 'cashier')
def pos(request):
    """Full POS terminal view for cashiers."""
    products = Product.objects.filter(is_active=True).select_related('category').order_by('name')
    categories = Category.objects.all()
    recent_transactions = Invoice.objects.order_by('-created_at')[:8]
    return render(request, 'pos/pos.html', {
        'products': products,
        'categories': categories,
        'recent_transactions': recent_transactions,
    })


@login_required
def pos_complete_sale(request):
    """AJAX endpoint — receive cart JSON, create Invoice and send to warehouse dispatch."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    import json as _json
    data = _json.loads(request.body)
    cart = data.get('cart', [])
    customer = data.get('customer_name', '').strip()
    account = data.get('account_number', '').strip()
    payment = data.get('payment_method', 'cash')
    notes = data.get('notes', '')

    if not cart:
        return JsonResponse({'error': 'Cart is empty'}, status=400)

    with transaction.atomic():
        invoice = Invoice.objects.create(
            invoice_number=gen_number('INV'),
            cashier=request.user,
            customer_name=customer,
            account_number=account,
            payment_method=payment,
            notes=notes,
            dispatch_status='pending',
        )
        for line in cart:
            try:
                product = Product.objects.get(pk=line['product_id'])
            except Product.DoesNotExist:
                transaction.set_rollback(True)
                return JsonResponse({'error': f"Product ID {line['product_id']} not found."}, status=400)
            qty = int(line['qty'])
            discount = Decimal(str(line.get('discount', 0)))
            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=qty,
                unit_price=product.unit_price,
                discount_percent=discount,
            )
        invoice.calculate_total()
    return JsonResponse({
        'success': True,
        'invoice_number': invoice.invoice_number,
        'total': str(invoice.total_amount),
        'invoice_id': invoice.pk,
    })


# ── QUOTES ────────────────────────────────────────────────────────────────────

@login_required
def quote_list(request):
    quotes = Quote.objects.select_related('cashier').order_by('-created_at')
    return render(request, 'pos/quote_list.html', {'quotes': quotes})


@login_required
def quote_new(request):
    products = Product.objects.filter(is_active=True).order_by('name')
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
    """Show the dispatch checklist for a single invoice."""
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.items.select_related('product').all()
    item_data = []
    for item in items:
        stock = item.product.current_stock
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
    """Confirm dispatch — deduct stock for each checked item, mark invoice dispatched."""
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method != 'POST':
        return redirect('warehouse_dispatch_detail', pk=pk)

    if invoice.dispatch_status == 'dispatched':
        messages.warning(request, 'This invoice has already been dispatched.')
        return redirect('warehouse_dispatch_detail', pk=pk)

    checked_item_ids = set(request.POST.getlist('checked_items'))
    items = list(invoice.items.select_related('product').all())

    # Collect dispatcher-entered quantities (may be partial for low-stock items)
    dispatch_quantities = {}
    for item in items:
        qty_str = request.POST.get(f'dispatch_qty_{item.pk}', '').strip()
        try:
            dqty = int(qty_str)
        except (ValueError, TypeError):
            dqty = item.quantity
        dispatch_quantities[item.pk] = dqty

    errors = []
    for item in items:
        if str(item.pk) not in checked_item_ids:
            errors.append(f"{item.product.name} has not been checked off.")
        else:
            dqty = dispatch_quantities[item.pk]
            if dqty <= 0:
                errors.append(f"Dispatch quantity for {item.product.name} must be at least 1.")
            elif dqty > item.product.current_stock:
                errors.append(
                    f"Dispatch quantity for {item.product.name} ({dqty}) exceeds available stock "
                    f"({item.product.current_stock} {item.product.unit})."
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
                    f"(stock available: {item.product.current_stock} {item.product.unit})"
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
    products = list(Product.objects.filter(is_active=True).select_related('category').values(
        'id', 'sku', 'name', 'unit_price', 'unit', 'category__name', 'barcode'
    ))
    # annotate stock
    for p in products:
        obj = Product.objects.get(pk=p['id'])
        p['stock'] = obj.current_stock
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

    products = Product.objects.filter(is_active=True)
    low_stock = [p for p in products if p.is_low_stock]
    out_of_stock = [p for p in products if p.current_stock <= 0]

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
    pallet_stock = []
    for p in all_pallets:
        pallet_stock.append({'pallet': p, 'location': p.current_location})

    context = {
        'total_pallets': total_pallets,
        'assigned_pallets': assigned_pallets,
        'unassigned_pallets': unassigned_pallets,
        'total_shelves': total_shelves,
        'occupied_shelves': occupied_shelves,
        'free_shelves': free_shelves,
        'low_stock': low_stock,
        'low_stock_count': len(low_stock),
        'out_of_stock': out_of_stock,
        'out_of_stock_count': len(out_of_stock),
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
            items = invoice.items.select_related('product').all()
            item_data = [{'item': i, 'current_stock': i.product.current_stock} for i in items]
            return render(request, 'warehouse/edit_order.html', {
                'invoice': invoice,
                'item_data': item_data,
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

    items = invoice.items.select_related('product').all()
    item_data = [{'item': i, 'current_stock': i.product.current_stock} for i in items]
    return render(request, 'warehouse/edit_order.html', {
        'invoice': invoice,
        'item_data': item_data,
    })
