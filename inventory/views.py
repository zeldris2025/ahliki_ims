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
                     StockMovement, Sale, SaleItem, StockAlert, PurchaseOrder, UserProfile)
from .forms import (ProductForm, SupplierForm, CategoryForm, GRNForm, GRNItemFormSet,
                    SaleForm, SaleItemFormSet, StockAdjustForm)


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
            # Redirect to POS or home, not dashboard (to avoid redirect loops)
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

    context = {
        'total_products': products.count(),
        'low_stock_count': len(low_stock),
        'low_stock_products': low_stock[:5],
        'open_alerts_count': open_alerts.count(),
        'open_alerts': open_alerts,
        'recent_sales': recent_sales,
        'recent_grns': recent_grns,
        'sales_today_total': sales_today_total,
        'sales_today_count': sales_today.count(),
        'sales_chart_json': json.dumps(sales_chart),
        'stock_value': stock_value,
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
@role_required('admin', 'warehouse')
def grn_list(request):
    grns = GoodsReceivedNote.objects.select_related('supplier', 'received_by').order_by('-received_at')
    return render(request, 'grn/list.html', {'grns': grns})


@login_required
@role_required('admin', 'warehouse')
def grn_add(request):
    form = GRNForm(request.POST or None)
    formset = GRNItemFormSet(request.POST or None)
    if form.is_valid() and formset.is_valid():
        with transaction.atomic():
            grn = form.save(commit=False)
            grn.received_by = request.user
            grn.save()
            items = formset.save(commit=False)
            for item in items:
                item.grn = grn
                item.save()
                # Create stock movement
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
            # Check for PO discrepancy
            if grn.purchase_order:
                grn.has_discrepancy = False
                for po_item in grn.purchase_order.items.all():
                    received = sum(i.quantity_received for i in grn.items.filter(product=po_item.product))
                    if received != po_item.quantity_ordered:
                        grn.has_discrepancy = True
                        StockAlert.objects.create(
                            product=po_item.product,
                            alert_type='discrepancy',
                            message=f"GRN {grn.grn_number}: ordered {po_item.quantity_ordered}, received {received} of {po_item.product.name}."
                        )
                grn.save()
        messages.success(request, f'GRN {grn.grn_number} saved. Stock updated.')
        return redirect('grn_detail', pk=grn.pk)
    return render(request, 'grn/form.html', {'form': form, 'formset': formset})


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
@role_required('admin')
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
    recent_transactions = Sale.objects.order_by('-created_at')[:8]
    return render(request, 'pos/pos.html', {
        'products': products,
        'categories': categories,
        'recent_transactions': recent_transactions,
    })


@login_required
def pos_complete_sale(request):
    """AJAX endpoint — receive cart JSON and save Sale + deduct stock."""
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

    errors = []
    with transaction.atomic():
        sale = Sale.objects.create(
            sale_number=gen_number('SAL'),
            cashier=request.user,
            customer_name=customer,
            account_number=account,
            payment_method=payment,
            notes=notes,
        )
        for line in cart:
            try:
                product = Product.objects.get(pk=line['product_id'])
            except Product.DoesNotExist:
                errors.append(f"Product ID {line['product_id']} not found.")
                continue
            qty = int(line['qty'])
            if product.current_stock < qty:
                errors.append(f"Insufficient stock for {product.name}. Available: {product.current_stock}")
                transaction.set_rollback(True)
                return JsonResponse({'error': '\n'.join(errors)}, status=400)
            SaleItem.objects.create(sale=sale, product=product, quantity=qty, unit_price=product.unit_price)
            StockMovement.objects.create(
                product=product, movement_type='out', quantity=-qty,
                reference=sale.sale_number, performed_by=request.user,
            )
            check_and_create_alerts(product)
        sale.calculate_total()
    return JsonResponse({'success': True, 'sale_number': sale.sale_number, 'total': str(sale.total_amount), 'sale_id': sale.pk})


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
        )
        for qi in quote.items.all():
            InvoiceItem.objects.create(
                invoice=invoice, product=qi.product,
                quantity=qi.quantity, unit_price=qi.unit_price,
                discount_percent=qi.discount_percent,
            )
            # Deduct stock
            if qi.product.current_stock < qi.quantity:
                messages.error(request, f"Not enough stock for {qi.product.name}. Conversion failed.")
                transaction.set_rollback(True)
                return redirect('quote_detail', pk=pk)
            StockMovement.objects.create(
                product=qi.product, movement_type='out', quantity=-qi.quantity,
                reference=invoice.invoice_number, performed_by=request.user,
            )
            check_and_create_alerts(qi.product)
        invoice.calculate_total()
        quote.status = 'converted'
        quote.converted_to = invoice
        quote.save()
    messages.success(request, f'Quote converted to Invoice {invoice.invoice_number}.')
    return redirect('invoice_detail', pk=invoice.pk)


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
