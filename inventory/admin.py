from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Case, Value, When
from django.utils.html import format_html, format_html_join
from .models import (AuditLog, UserProfile, Supplier, Category, Product, PurchaseOrder,
                     PurchaseOrderItem, GoodsReceivedNote, GRNItem,
                     StockMovement, Sale, SaleItem, StockAlert,
                     Container, ContainerItem, ContainerComment, ContainerType, ShipmentTracking)
from .csv_import import CSVImportMixin, to_bool, to_decimal, to_int

admin.site.site_header = "Ah Liki IMS Admin"
admin.site.site_title = "Ah Liki IMS"

# ── Staff, grouped by the side of the business they work on ──────────────────

def department_case(superuser='is_superuser', role='profile__role'):
    """SQL expression giving each staff member's department key, matching
    UserProfile.department. The arguments are the paths to User.is_superuser
    and UserProfile.role from the model being listed."""
    whens = [When(**{superuser: True}, then=Value('management'))]
    whens += [When(**{f'{role}__in': UserProfile.roles_in_department(dept)}, then=Value(dept))
              for dept, _ in UserProfile.DEPARTMENT_CHOICES]
    return Case(*whens, default=Value('management'))


# Departments in the order they are listed, for sorting staff into groups.
DEPARTMENT_ORDER = Case(*[When(dept_key=dept, then=Value(i))
                          for i, (dept, _) in enumerate(UserProfile.DEPARTMENT_CHOICES)])


class DepartmentFilter(admin.SimpleListFilter):
    """Filter staff by department (Warehouse, Containers, Sales…) — the
    queryset must be annotated with `dept_key` (see department_case)."""
    title = 'department'
    parameter_name = 'department'

    def lookups(self, request, model_admin):
        return UserProfile.DEPARTMENT_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(dept_key=self.value())
        return queryset


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Role & department'
    fields = ['role', 'department_name']
    readonly_fields = ['department_name']

    @admin.display(description='Department')
    def department_name(self, obj):
        return obj.get_department_display() if obj.pk else 'Set by role when saved'


admin.site.unregister(User)


@admin.register(User)
class StaffUserAdmin(UserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'full_name', 'department', 'role', 'is_active', 'last_login']
    list_filter = [DepartmentFilter, 'profile__role', 'is_active', 'is_superuser']
    list_select_related = ['profile']

    def get_queryset(self, request):
        # Built here rather than via super(), which orders before dept_order exists.
        qs = self.model._default_manager.annotate(dept_key=department_case()).annotate(dept_order=DEPARTMENT_ORDER)
        return qs.order_by(*self.get_ordering(request))

    def get_ordering(self, request):
        return ['dept_order', 'username']  # annotated in get_queryset, so not allowed in `ordering`

    @admin.display(description='Full name', ordering='first_name')
    def full_name(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description='Department', ordering='dept_order')
    def department(self, obj):
        return dict(UserProfile.DEPARTMENT_CHOICES)[obj.dept_key]

    @admin.display(description='Role', ordering='profile__role')
    def role(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.get_role_display() if profile else '—'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'role']
    list_filter = [DepartmentFilter, 'role']
    list_select_related = ['user']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']

    def get_queryset(self, request):
        # Built here rather than via super(), which orders before dept_order exists.
        qs = self.model._default_manager.annotate(dept_key=department_case('user__is_superuser', 'role')).annotate(dept_order=DEPARTMENT_ORDER)
        return qs.order_by(*self.get_ordering(request))

    def get_ordering(self, request):
        return ['dept_order', 'user__username']  # annotated in get_queryset, so not allowed in `ordering`

    @admin.display(description='Department', ordering='dept_order')
    def department(self, obj):
        return dict(UserProfile.DEPARTMENT_CHOICES)[obj.dept_key]


# ── Audit log (read-only: nobody can add, edit or delete entries) ─────────────

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'who', 'department', 'action_badge', 'area', 'object_type', 'object_repr', 'ip_address']
    list_filter = ['department', 'action', 'area', 'role', 'timestamp']
    search_fields = ['username', 'object_repr', 'object_type', 'object_id', 'ip_address', 'path']
    date_hierarchy = 'timestamp'
    list_per_page = 100
    fields = ['timestamp', 'who', 'role_name', 'department', 'action', 'area', 'object_type', 'object_id',
              'object_repr', 'changes_table', 'ip_address', 'path']
    readonly_fields = fields

    ACTION_COLOURS = {'create': '#166534', 'update': '#1e40af', 'delete': '#991b1b',
                      'login': '#374151', 'logout': '#374151', 'login_failed': '#b45309'}

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='User', ordering='username')
    def who(self, obj):
        return obj.username or 'System'

    @admin.display(description='Role')
    def role_name(self, obj):
        return dict(UserProfile.ROLE_CHOICES).get(obj.role, obj.role or '—')

    @admin.display(description='Action', ordering='action')
    def action_badge(self, obj):
        return format_html('<strong style="color:{}">{}</strong>',
                           self.ACTION_COLOURS.get(obj.action, '#374151'), obj.get_action_display())

    @admin.display(description='Changes')
    def changes_table(self, obj):
        if not obj.changes:
            return '—'
        rows = format_html_join('', '<tr><th>{}</th><td>{}</td><td>{}</td></tr>',
                                ((field.replace('_', ' '), old or '—', new or '—')
                                 for field, (old, new) in obj.changes.items()))
        return format_html('<table><thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead>'
                           '<tbody>{}</tbody></table>', rows)

@admin.register(Supplier)
class SupplierAdmin(CSVImportMixin, admin.ModelAdmin):
    list_display = ['name', 'contact_name', 'phone', 'email']
    search_fields = ['name', 'contact_name', 'email']

    csv_columns = [
        ('name', True, 'Supplier name — the unique key. Re-using a name updates that supplier.'),
        ('contact_name', False, 'Person to contact.'),
        ('phone', False, 'Phone number.'),
        ('email', False, 'Email address.'),
        ('address', False, 'Postal address.'),
    ]
    csv_sample_rows = [
        ['Pacific Foods Ltd', 'John Tavita', '+685 22334', 'sales@pacificfoods.ws', 'Vaitele, Apia'],
        ['Samoa Beverages', 'Mele Fa\'aui', '+685 55667', 'orders@samoabev.ws', 'Sogi, Apia'],
    ]

    def import_csv_row(self, row):
        name = row.get('name', '')
        if not name:
            raise ValueError('name is required')
        supplier, created = Supplier.objects.get_or_create(name=name)
        for field in ('contact_name', 'phone', 'email', 'address'):
            if row.get(field):
                setattr(supplier, field, row[field])
        supplier.save()
        return 'created' if created else 'updated'


@admin.register(Category)
class CategoryAdmin(CSVImportMixin, admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

    csv_columns = [
        ('name', True, 'Category name — the unique key. Re-using a name updates that category.'),
        ('description', False, 'Free-text description.'),
    ]
    csv_sample_rows = [
        ['Beverages', 'Soft drinks, juices and water'],
        ['Dry Goods', 'Rice, flour, sugar and other shelf-stable goods'],
    ]

    def import_csv_row(self, row):
        name = row.get('name', '')
        if not name:
            raise ValueError('name is required')
        category, created = Category.objects.get_or_create(name=name)
        if row.get('description'):
            category.description = row['description']
            category.save()
        return 'created' if created else 'updated'


@admin.register(Product)
class ProductAdmin(CSVImportMixin, admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'supplier', 'unit_price', 'reorder_level', 'is_active']
    list_filter = ['category', 'supplier', 'is_active']
    search_fields = ['sku', 'name', 'barcode']

    csv_columns = [
        ('sku', True, 'Product code — the unique key. Re-using an SKU updates that product.'),
        ('name', True, 'Product name.'),
        ('category', False, 'Category name. Created automatically if it does not exist yet.'),
        ('supplier', False, 'Supplier name. Created automatically if it does not exist yet.'),
        ('unit_price', False, 'Selling price, e.g. 12.50. Defaults to 0.'),
        ('cost_price', False, 'Buying price, e.g. 8.00. Defaults to 0.'),
        ('reorder_level', False, 'Whole number — alert when stock falls to or below it. Defaults to 10.'),
        ('unit', False, 'Unit of measure, e.g. each, kg, carton. Defaults to "each".'),
        ('barcode', False, 'Barcode number.'),
        ('description', False, 'Free-text description.'),
        ('is_active', False, 'yes/no (also accepts true/false or 1/0). Defaults to yes.'),
    ]
    csv_sample_rows = [
        ['BEV-001', 'Cola 1.5L', 'Beverages', 'Samoa Beverages', '8.50', '6.00', '24', 'each',
         '9412345678901', 'Bottled cola, 1.5 litre', 'yes'],
        ['DRY-001', 'Rice 10kg', 'Dry Goods', 'Pacific Foods Ltd', '45.00', '36.00', '10', 'bag',
         '', 'Long grain white rice', 'yes'],
    ]

    def import_csv_row(self, row):
        sku = row.get('sku', '')
        name = row.get('name', '')
        if not sku:
            raise ValueError('sku is required')
        if not name:
            raise ValueError('name is required')

        product, created = Product.objects.get_or_create(
            sku=sku, defaults={'name': name, 'unit_price': 0})
        product.name = name

        if row.get('category'):
            product.category = Category.objects.get_or_create(name=row['category'])[0]
        if row.get('supplier'):
            product.supplier = Supplier.objects.get_or_create(name=row['supplier'])[0]
        if row.get('unit_price') or created:
            product.unit_price = to_decimal(row.get('unit_price'))
        if row.get('cost_price') or created:
            product.cost_price = to_decimal(row.get('cost_price'))
        if row.get('reorder_level') or created:
            product.reorder_level = to_int(row.get('reorder_level'), 10)
        if row.get('unit'):
            product.unit = row['unit']
        if row.get('barcode'):
            product.barcode = row['barcode']
        if row.get('description'):
            product.description = row['description']
        if row.get('is_active'):
            product.is_active = to_bool(row['is_active'])

        product.full_clean(exclude=['category', 'supplier'])
        product.save()
        return 'created' if created else 'updated'

class GRNItemInline(admin.TabularInline):
    model = GRNItem
    extra = 1

@admin.register(GoodsReceivedNote)
class GRNAdmin(admin.ModelAdmin):
    list_display = ['grn_number', 'supplier', 'received_by', 'received_at', 'has_discrepancy']
    inlines = [GRNItemInline]

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'product', 'movement_type', 'quantity', 'reference', 'performed_by']
    list_filter = ['movement_type']

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['sale_number', 'cashier', 'customer_name', 'total_amount', 'payment_method', 'created_at']
    inlines = [SaleItemInline]

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['alert_type', 'product', 'is_resolved', 'created_at']
    list_filter = ['alert_type', 'is_resolved']


class ContainerItemInline(admin.TabularInline):
    model = ContainerItem
    extra = 1


class ContainerCommentInline(admin.TabularInline):
    model = ContainerComment
    extra = 0


@admin.register(ContainerType)
class ContainerTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    list_editable = ['is_active']


@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
    list_display = ['container_number', 'container_type', 'supplier', 'status', 'arrival_date',
                    'created_by', 'checked_in_at', 'opened_at', 'closed_at']
    list_filter = ['status', 'supplier', 'container_type']
    search_fields = ['container_number', 'vessel', 'container_type__name']
    inlines = [ContainerItemInline, ContainerCommentInline]


@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(admin.ModelAdmin):
    list_display = ['request_number', 'request_type', 'scac', 'vessel_name', 'origin_port', 'eta_at',
                    'arrived_at', 't49_status', 'show_in_my_containers', 'last_synced_at']
    list_filter = ['t49_status', 'request_type', 'show_in_my_containers']
    search_fields = ['request_number', 'vessel_name', 'container_numbers']
    readonly_fields = ['t49_request_id', 't49_shipment_id', 'last_synced_at', 'last_sync_message', 'created_at']


# ── CMS — Container Management ────────────────────────────────────────────────
from .models import CmsContainer, ContainerReturn, ShippingLine, Yard  # noqa: E402


@admin.register(Yard)
class YardAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'latitude', 'longitude', 'is_active', 'sort_order']
    list_editable = ['is_active', 'sort_order']
    search_fields = ['code', 'description']


@admin.register(ShippingLine)
class ShippingLineAdmin(admin.ModelAdmin):
    list_display = ['name', 'return_days']
    search_fields = ['name']


class ContainerReturnInline(admin.TabularInline):
    model = ContainerReturn
    extra = 0
    readonly_fields = ['location', 'created_at']


@admin.register(CmsContainer)
class CmsContainerAdmin(admin.ModelAdmin):
    list_display = ['code', 'yard', 'status', 'owner', 'vessel_voyage', 'arrival_date', 'driver', 'returned']
    list_filter = ['returned', 'status', 'yard', 'owner']
    search_fields = ['code', 'description', 'vessel_voyage', 'driver', 'note']
    date_hierarchy = 'arrival_date'
    inlines = [ContainerReturnInline]


@admin.register(ContainerReturn)
class ContainerReturnAdmin(admin.ModelAdmin):
    list_display = ['container', 'yard', 'status', 'location', 'returned_date', 'staff_name', 'driver']
    list_filter = ['status', 'yard']
    search_fields = ['container__code', 'staff_name', 'driver']


from .models import ContainerTransfer  # noqa: E402


@admin.register(ContainerTransfer)
class ContainerTransferAdmin(admin.ModelAdmin):
    list_display = ['container', 'from_yard', 'to_yard', 'transferred_date', 'driver', 'staff_name', 'note']
    list_filter = ['from_yard', 'to_yard']
    search_fields = ['container__code', 'driver', 'staff_name', 'note']
