from django.urls import path

from . import views

app_name = 'sda_school'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('academics/', views.academics, name='academics'),
    path('spiritual-life/', views.spiritual_life, name='spiritual_life'),
    path('admissions/', views.admissions, name='admissions'),
    path('news/', views.news, name='news'),
    path('contact/', views.contact, name='contact'),
]
