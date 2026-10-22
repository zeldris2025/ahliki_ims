from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.conf import settings
from inventory import views as inventory_views


def home_redirect(request):
    """Redirect to appropriate home page based on user role."""
    # Handle unauthenticated users directly — do NOT use @login_required here,
    # because the login view has redirect_authenticated_user=True which would
    # create an infinite loop: / -> /login/ -> / -> /login/ -> ...
    if not request.user.is_authenticated:
        return redirect('login')

    from inventory.models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Superusers and staff roles go to the dashboard
    if request.user.is_superuser or profile.role in ['admin', 'finance', 'warehouse']:
        return redirect('dashboard')

    if profile.role in ['manager']:
        return redirect('manager_dashboard')

    if profile.role == 'wms_operator':
        return redirect('wms_dashboard')

    if profile.role == 'wms_dispatcher':
        return redirect('wms_dispatcher_dashboard')

    if profile.role == 'custom_broker':
        return redirect('cms_dashboard')

    # Cashiers go to invoice upload
    return redirect('invoice_upload')


urlpatterns = [
    path('admin/', admin.site.urls),

    # Remove redirect_authenticated_user=True — it was the root cause of the
    # infinite redirect loop when combined with @login_required on home_redirect.
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('', home_redirect, name='home'),
    path('', include('inventory.urls')),
    # Uploaded files (invoices). static() only works with DEBUG on, so serve them explicitly —
    # behind the login, since the site is reachable from the internet once it is on Azure.
    re_path(r'^media/(?P<path>.*)$', login_required(serve), {'document_root': settings.MEDIA_ROOT}),
]