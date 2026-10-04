from django.contrib import admin
from .models import (UserProfile, Supplier, Category, Product, PurchaseOrder,
                     PurchaseOrderItem, GoodsReceivedNote, GRNItem,
                     StockMovement, Sale, SaleItem, StockAlert,
                     Container, ContainerItem, ContainerComment, ContainerType)
from .csv_import import CSVImportMixin, to_bool, to_decimal, to_int

admin.site.site_header = "Ah Liki IMS Admin"
admin.site.site_title = "Ah Liki IMS"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']

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
