from django.urls import path
from django.views.generic import RedirectView
from . import views, cms_views

urlpatterns = [
    
    path('dashboard/', views.dashboard, name='dashboard'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/lookup/', views.stock_lookup, name='stock_lookup'),
    path('products/lookup/search/', views.stock_lookup_search, name='stock_lookup_search'),
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

    # Invoice Upload (replaces POS)
    path('invoices/upload/', views.invoice_upload, name='invoice_upload'),
    path('invoices/parse-pdf/', views.invoice_parse_pdf, name='invoice_parse_pdf'),



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
    path('wms/shelves/add/', views.shelf_add, name='shelf_add'),
    path('wms/shelves/<str:shelf_code>/edit/', views.shelf_edit, name='shelf_edit'),

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

    # Containers — Customs Broker
    # The old broker list — containers are now worked from Warehouse → Containers.
    path('containers/', RedirectView.as_view(pattern_name='warehouse_container_list'), name='container_list'),
    path('containers/new/', views.container_create, name='container_create'),
    path('containers/<int:pk>/', views.container_detail, name='container_detail'),
    path('containers/<int:pk>/edit/', views.container_edit, name='container_edit'),
    path('containers/<int:pk>/comment/', views.container_add_comment, name='container_add_comment'),

    # Track Containers (Terminal49) + Ah Liki Atlas — Customs Broker
    path('containers/track/', views.track_list, name='track_list'),
    path('containers/track/refresh/', views.track_refresh, name='track_refresh_all'),
    path('containers/track/<int:pk>/', views.track_edit, name='track_edit'),
    path('containers/track/<int:pk>/refresh/', views.track_refresh, name='track_refresh'),
    path('containers/track/<int:pk>/toggle/', views.track_toggle, name='track_toggle'),
    path('containers/track/<int:pk>/delete/', views.track_delete, name='track_delete'),
    path('containers/atlas/', views.atlas, name='atlas'),
    path('containers/atlas/data/', views.atlas_data, name='atlas_data'),

    # CMS — Container Management (Customs Broker)
    path('cms/', cms_views.dashboard, name='cms_dashboard'),
    path('cms/containers/', cms_views.container_list, name='cms_containers'),
    path('cms/containers/add/', cms_views.container_add, name='cms_container_add'),
    path('cms/containers/bulk/', cms_views.container_bulk, name='cms_container_bulk'),
    path('cms/containers/import/', cms_views.container_import, name='cms_container_import'),
    path('cms/containers/import/template/', cms_views.container_import_template, name='cms_import_template'),
    path('cms/containers/<int:pk>/', cms_views.container_edit, name='cms_container_edit'),
    path('cms/containers/<int:pk>/transfer/', cms_views.container_transfer, name='cms_container_transfer'),
    path('cms/containers/<int:pk>/return/', cms_views.container_return, name='cms_container_return'),
    path('cms/containers/<int:pk>/delete/', cms_views.container_delete, name='cms_container_delete'),
    path('cms/shipping/', cms_views.shipping, name='cms_shipping'),
    path('cms/shipping/<int:pk>/', cms_views.shipping, name='cms_shipping_edit'),
    path('cms/shipping/<int:pk>/delete/', cms_views.shipping_delete, name='cms_shipping_delete'),
    path('cms/returned/', cms_views.returns, name='cms_returns'),
    path('cms/returned/<int:pk>/undo/', cms_views.return_undo, name='cms_return_undo'),
    path('cms/atlas/', cms_views.atlas, name='cms_atlas'),
    path('cms/atlas/yard/<int:pk>/move/', cms_views.yard_move, name='cms_yard_move'),

    # Containers — Warehouse
    path('warehouse/containers/', views.warehouse_container_list, name='warehouse_container_list'),
    path('warehouse/containers/<int:pk>/check-in/', views.container_check_in, name='container_check_in'),
    path('warehouse/containers/<int:pk>/open/', views.container_open, name='container_open'),
    path('warehouse/containers/<int:pk>/palletize/<int:item_pk>/', views.container_palletize, name='container_palletize'),
    path('warehouse/containers/<int:pk>/close/', views.container_close, name='container_close'),
    path('warehouse/containers/<int:pk>/reopen/', views.container_reopen, name='container_reopen'),

    # WMS — API
    path('api/pallet/<str:lot_number>/', views.api_pallet_lookup, name='api_pallet_lookup'),
]