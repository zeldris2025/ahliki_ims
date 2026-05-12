from django.contrib import admin
from .models import (UserProfile, Supplier, Category, Product, PurchaseOrder,
                     PurchaseOrderItem, GoodsReceivedNote, GRNItem,
                     StockMovement, Sale, SaleItem, StockAlert)

admin.site.site_header = "Ah Liki IMS Admin"
admin.site.site_title = "Ah Liki IMS"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_name', 'phone', 'email']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'supplier', 'unit_price', 'reorder_level', 'is_active']
    list_filter = ['category', 'supplier', 'is_active']
    search_fields = ['sku', 'name', 'barcode']

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
