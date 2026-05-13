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
]