from django.urls import path
from . import views

urlpatterns = [
    
    path('dashboard/', views.dashboard, name='dashboard'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),

    # Suppliers / Categories
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_add, name='supplier_add'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_add, name='category_add'),

    # GRN
    path('grn/', views.grn_list, name='grn_list'),
    path('grn/add/', views.grn_add, name='grn_add'),
    path('grn/<int:pk>/', views.grn_detail, name='grn_detail'),

    # Legacy sales form
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/add/', views.sale_new, name='sale_new'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),

    # POS terminal
    path('pos/', views.pos, name='pos'),
    path('pos/complete/', views.pos_complete_sale, name='pos_complete_sale'),

    # Quotes
    path('quotes/', views.quote_list, name='quote_list'),
    path('quotes/new/', views.quote_new, name='quote_new'),
    path('quotes/<int:pk>/', views.quote_detail, name='quote_detail'),
    path('quotes/<int:pk>/convert/', views.quote_convert, name='quote_convert'),

    # Invoices
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/pay/', views.invoice_mark_paid, name='invoice_mark_paid'),

    # Warehouse Dispatch
    path('warehouse/dispatch/', views.warehouse_dispatch_list, name='warehouse_dispatch_list'),
    path('warehouse/dispatch/export/', views.warehouse_dispatch_export, name='warehouse_dispatch_export'),
    path('warehouse/dispatch/<int:pk>/', views.warehouse_dispatch_detail, name='warehouse_dispatch_detail'),
    path('warehouse/dispatch/<int:pk>/submit/', views.warehouse_dispatch_submit, name='warehouse_dispatch_submit'),

    # Stock
    path('stock/movements/', views.stock_movements, name='stock_movements'),
    path('stock/adjust/', views.stock_adjust, name='stock_adjust'),

    # Alerts
    path('alerts/', views.alert_list, name='alert_list'),
    path('alerts/<int:pk>/resolve/', views.alert_resolve, name='alert_resolve'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/export/stock/', views.export_stock_csv, name='export_stock_csv'),
    path('reports/export/sales/', views.export_sales_csv, name='export_sales_csv'),

    # Users
    path('profile/', views.profile, name='profile'),
    path('profile/password/', views.change_password, name='change_password'),
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.user_add, name='user_add'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),

    # API
    path('api/product/<str:sku>/', views.api_product_lookup, name='api_product_lookup'),
    path('api/products/', views.api_products_all, name='api_products_all'),

    # WMS — Pallets
    path('wms/pallets/', views.pallet_list, name='pallet_list'),
    path('wms/pallets/create/', views.pallet_create, name='pallet_create'),
    path('wms/pallets/<int:pk>/label/', views.pallet_label, name='pallet_label'),
    path('wms/pallets/<str:lot_number>/edit/', views.pallet_edit, name='pallet_edit'),

    # WMS — Shelves
    path('wms/shelves/', views.shelf_list, name='shelf_list'),
    path('wms/shelves/qr-print/', views.shelf_qr_print, name='shelf_qr_print'),

    # WMS — Check-In
    path('wms/checkin/', views.wms_checkin, name='wms_checkin'),
    path('wms/checkin/<str:shelf_code>/', views.wms_checkin, name='wms_checkin_shelf'),

    # WMS — Transfer
    path('wms/transfer/', views.wms_transfer, name='wms_transfer'),

    # WMS — Picking Ticket
    path('wms/picking/<int:invoice_pk>/', views.picking_ticket, name='picking_ticket'),

    # WMS — Manager Dashboard
    path('wms/manager/', views.manager_dashboard, name='manager_dashboard'),

    # WMS Operator Dashboard
    path('wms/', views.wms_dashboard, name='wms_dashboard'),

    # WMS Dispatcher Dashboard
    path('wms/dispatcher/', views.wms_dispatcher_dashboard, name='wms_dispatcher_dashboard'),

    # Dispatch — Comment & Edit Order
    path('warehouse/dispatch/<int:pk>/comment/', views.dispatcher_add_comment, name='dispatcher_add_comment'),
    path('warehouse/dispatch/<int:pk>/edit/', views.dispatcher_edit_order, name='dispatcher_edit_order'),

    # WMS — API
    path('api/pallet/<str:lot_number>/', views.api_pallet_lookup, name='api_pallet_lookup'),
]