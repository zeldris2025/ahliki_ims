from django.db import models
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('finance', 'Finance'),
        ('warehouse', 'Warehouse Lead'),
        ('wms_operator', 'WMS Operator'),
        ('wms_dispatcher', 'WMS Dispatcher'),
        ('cashier', 'Sales / Cashier'),
        ('custom_broker', 'Customs Broker'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cashier')

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, related_name='products')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reorder_level = models.PositiveIntegerField(default=10, help_text='Alert when stock falls below this')
    unit = models.CharField(max_length=50, default='each', help_text='e.g. each, kg, litre, carton')
    barcode = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sku} — {self.name}"

    @property
    def current_stock(self):
        result = self.stock_movements.aggregate(total=models.Sum('quantity'))
        return result['total'] or 0

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level

    @property
    def stock_value(self):
        return self.current_stock * self.cost_price


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('partial', 'Partially Received'),
        ('cancelled', 'Cancelled'),
    ]
    po_number = models.CharField(max_length=100, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.po_number


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.purchase_order.po_number} — {self.product.name}"


class GoodsReceivedNote(models.Model):
    grn_number = models.CharField(max_length=100, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='grns')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='grns')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    received_at = models.DateTimeField(default=timezone.now)
    has_discrepancy = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.grn_number


class GRNItem(models.Model):
    grn = models.ForeignKey(GoodsReceivedNote, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_received = models.PositiveIntegerField()
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.grn.grn_number} — {self.product.name}"


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text='Positive for in, negative for out')
    reference = models.CharField(max_length=200, blank=True, help_text='GRN or Sale number')
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.product.sku} {self.movement_type} {self.quantity} @ {self.timestamp:%d/%m/%Y}"


class Sale(models.Model):
    sale_number = models.CharField(max_length=100, unique=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales')
    created_at = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    customer_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=100, blank=True, help_text='BC account for credit customers')
    payment_method = models.CharField(max_length=50, default='cash',
        choices=[('cash','Cash'),('credit','Credit Account'),('eftpos','EFTPOS')])
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.sale_number

    def calculate_total(self):
        total = sum(item.line_total for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=['total_amount'])
        return total


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.sale.sale_number} — {self.product.name} x{self.quantity}"


class StockAlert(models.Model):
    ALERT_TYPES = [
        ('low_stock', 'Low Stock'),
        ('expiry', 'Expiry Warning'),
        ('discrepancy', 'GRN Discrepancy'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.get_alert_type_display()} — {self.product.name}"


class Quote(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('converted', 'Converted to Invoice'),
        ('expired', 'Expired'),
    ]
    quote_number = models.CharField(max_length=100, unique=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='quotes')
    customer_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    converted_to = models.OneToOneField('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='from_quote')

    def __str__(self):
        return self.quote_number

    def calculate_total(self):
        total = sum(item.line_total for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=['total_amount'])
        return total


class QuoteItem(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    @property
    def line_total(self):
        discounted = self.unit_price * (1 - self.discount_percent / 100)
        return self.quantity * discounted

    def __str__(self):
        return f"{self.quote.quote_number} — {self.product.name}"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('void', 'Void'),
    ]
    DISPATCH_STATUS_CHOICES = [
        ('pending', 'Pending Dispatch'),
        ('dispatched', 'Dispatched'),
    ]
    invoice_number = models.CharField(max_length=100, unique=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='invoices')
    customer_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, default='cash',
        choices=[('cash','Cash'),('credit','Credit Account'),('eftpos','EFTPOS'),('cheque','Cheque')])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    dispatch_status = models.CharField(max_length=20, choices=DISPATCH_STATUS_CHOICES, default='pending')
    dispatched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatched_invoices')
    dispatched_at = models.DateTimeField(null=True, blank=True)
    truck_plate = models.CharField(max_length=50, blank=True, help_text='Delivery truck plate number')
    created_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Uploaded invoice fields
    invoice_file = models.FileField(upload_to='invoices/', blank=True, null=True)
    salesperson = models.CharField(max_length=100, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True, help_text='e.g. Net 7 days')
    sales_territory = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.invoice_number

    def calculate_total(self):
        subtotal = sum(item.line_total for item in self.items.all())
        self.tax_amount = round(subtotal * Decimal('0.15'), 2)
        self.total_amount = subtotal + self.tax_amount
        self.save(update_fields=['total_amount', 'tax_amount'])
        return self.total_amount


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    @property
    def line_total(self):
        discounted = self.unit_price * (1 - self.discount_percent / 100)
        return self.quantity * discounted

    def __str__(self):
        return f"{self.invoice.invoice_number} — {self.product.name}"


# ── WMS: PALLETS & SHELF LOCATIONS ────────────────────────────────────────────

class ShelfLocation(models.Model):
    code = models.CharField(max_length=10, unique=True)   # e.g. A1, B2, Z3
    letter = models.CharField(max_length=1)                # A–Z
    story = models.PositiveSmallIntegerField()             # 1, 2, or 3

    class Meta:
        ordering = ['letter', 'story']

    def __str__(self):
        return self.code

    def current_pallets(self):
        return Pallet.objects.filter(
            location_history__shelf=self,
            location_history__is_current=True,
        )


class Pallet(models.Model):
    lot_number = models.CharField(max_length=100, unique=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='pallets')
    grn_item = models.ForeignKey(GRNItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='pallets')
    container_item = models.ForeignKey('ContainerItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='pallets')
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pallets_created')
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.lot_number

    @property
    def current_location(self):
        assignment = self.location_history.filter(is_current=True).first()
        return assignment.shelf if assignment else None


class PalletLocation(models.Model):
    pallet = models.ForeignKey(Pallet, on_delete=models.CASCADE, related_name='location_history')
    shelf = models.ForeignKey(ShelfLocation, on_delete=models.CASCADE, related_name='pallet_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='shelf_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.pallet.lot_number} @ {self.shelf.code}"


class DispatchComment(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on {self.invoice.invoice_number} by {self.author}"


# ── CONTAINERS: WHARF → HQ → OPEN → PALLETIZE → CLOSE ─────────────────────────

class ContainerType(models.Model):
    """A type of container — the shipping line plus the size, e.g. 'Matson 40 FT'.
    Maintained in the admin panel and offered as a dropdown when lodging a container."""

    name = models.CharField(max_length=120, unique=True,
                            help_text='Name and size, e.g. Matson 40 FT')
    is_active = models.BooleanField(default=True,
                                    help_text='Untick to hide this type from the dropdown')

    class Meta:
        ordering = ['name']
        verbose_name = 'Container type'
        verbose_name_plural = 'Container types'

    def __str__(self):
        return self.name


class Container(models.Model):
    """A shipping container lodged by the customs broker at the wharf and then
    tracked through check-in at HQ, opening, palletizing and closing."""

    STATUS_AT_WHARF = 'at_wharf'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_OPENED = 'opened'
    STATUS_PALLETIZED = 'palletized'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_AT_WHARF, 'At Wharf'),
        (STATUS_CHECKED_IN, 'Checked In at HQ'),
        (STATUS_OPENED, 'Opened'),
        (STATUS_PALLETIZED, 'Palletized'),
        (STATUS_CLOSED, 'Closed'),
    ]

    # Ordered flow — used to compare progress.
    STATUS_ORDER = [STATUS_AT_WHARF, STATUS_CHECKED_IN, STATUS_OPENED,
                    STATUS_PALLETIZED, STATUS_CLOSED]

    container_number = models.CharField(max_length=100, unique=True,
                                        help_text='e.g. MSKU1234567')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='containers')
    container_type = models.ForeignKey(ContainerType, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='containers', verbose_name='Type of container')
    vessel = models.CharField(max_length=200, blank=True, help_text='Vessel / voyage name')
    arrival_date = models.DateField(null=True, blank=True, help_text='Date the container landed at the wharf')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AT_WHARF)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='containers_lodged')
    created_at = models.DateTimeField(auto_now_add=True)

    checked_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='containers_checked_in')
    checked_in_at = models.DateTimeField(null=True, blank=True)

    opened_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='containers_opened')
    opened_at = models.DateTimeField(null=True, blank=True)

    palletized_at = models.DateTimeField(null=True, blank=True)

    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='containers_closed')
    closed_at = models.DateTimeField(null=True, blank=True)

    # GRN generated when the container is opened — this is what puts stock on hand.
    grn = models.OneToOneField(GoodsReceivedNote, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='container')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.container_number

    def status_rank(self):
        try:
            return self.STATUS_ORDER.index(self.status)
        except ValueError:
            return 0

    def has_reached(self, status):
        return self.status_rank() >= self.STATUS_ORDER.index(status)

    @property
    def is_editable(self):
        """The broker may only amend the manifest before the container is opened."""
        return self.status in (self.STATUS_AT_WHARF, self.STATUS_CHECKED_IN)

    @property
    def total_quantity(self):
        return self.items.aggregate(t=models.Sum('quantity'))['t'] or 0

    @property
    def palletized_quantity(self):
        return Pallet.objects.filter(container_item__container=self).aggregate(
            t=models.Sum('quantity'))['t'] or 0

    @property
    def remaining_quantity(self):
        return max(self.total_quantity - self.palletized_quantity, 0)

    @property
    def is_fully_palletized(self):
        return self.items.exists() and self.remaining_quantity == 0

    def refresh_palletized_status(self):
        """Move to (or back from) the 'palletized' status as pallets are built."""
        if self.status == self.STATUS_OPENED and self.is_fully_palletized:
            self.status = self.STATUS_PALLETIZED
            self.palletized_at = timezone.now()
            self.save(update_fields=['status', 'palletized_at'])
        elif self.status == self.STATUS_PALLETIZED and not self.is_fully_palletized:
            self.status = self.STATUS_OPENED
            self.palletized_at = None
            self.save(update_fields=['status', 'palletized_at'])


class ContainerItem(models.Model):
    """A line on the container manifest, entered by the customs broker."""
    container = models.ForeignKey(Container, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='container_items')
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    # Set when the container is opened and the GRN is generated.
    grn_item = models.ForeignKey(GRNItem, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='container_items')

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return f"{self.container.container_number} — {self.product.name} x{self.quantity}"

    @property
    def palletized_quantity(self):
        return self.pallets.aggregate(t=models.Sum('quantity'))['t'] or 0

    @property
    def remaining_quantity(self):
        return max(self.quantity - self.palletized_quantity, 0)

    @property
    def is_fully_palletized(self):
        return self.remaining_quantity == 0


class ContainerComment(models.Model):
    """Notes against a container — used for damage/breakage reports raised
    after unloading and before the container is closed."""
    container = models.ForeignKey(Container, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    is_damage = models.BooleanField(default=False, help_text='Flag as a damaged / broken goods report')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on {self.container.container_number} by {self.author}"
