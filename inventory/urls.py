from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),

    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_add, name='supplier_add'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_add, name='category_add'),

    # GRN
    path('grn/', views.grn_list, name='grn_list'),
    path('grn/add/', views.grn_add, name='grn_add'),
    path('grn/<int:pk>/', views.grn_detail, name='grn_detail'),

    # Sales
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/new/', views.sale_new, name='sale_new'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),

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

    # User profiles & management
    path('profile/', views.profile, name='profile'),
    path('profile/password/', views.change_password, name='change_password'),
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.user_add, name='user_add'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),

    # API
    path('api/product/<str:sku>/', views.api_product_lookup, name='api_product_lookup'),
]
