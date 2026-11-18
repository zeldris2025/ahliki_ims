from django.urls import path

from . import views

app_name = 'ls_central'

urlpatterns = [
    path('', views.status, name='status'),
    path('sync/', views.sync_now, name='sync'),
    path('test/', views.test_connection, name='test'),
]
