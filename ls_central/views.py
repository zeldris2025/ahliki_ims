from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from inventory.views import role_required

from .client import LsCentralClient, LsCentralError, missing_settings
from .models import LsCentralInvoice, LsCentralSync
from .sync import sync_invoices

DISPATCH_ROLES = ('admin', 'warehouse', 'wms_dispatcher')


def is_ls_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)   # a missing profile raises AttributeError → None
    return getattr(profile, 'role', '') == 'admin'


def _back(request, default='ls_central:status'):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        return redirect(nxt)
    return redirect(default)


@login_required
@role_required('admin')
def status(request):
    """Connection settings (never the secret), recent syncs and imported invoices."""
    secret = settings.LS_CENTRAL_CLIENT_SECRET
    rows = [
        ('Tenant ID', settings.LS_CENTRAL_TENANT_ID),
        ('Client ID', settings.LS_CENTRAL_CLIENT_ID),
        ('Client secret', f'set ({len(secret)} characters, hidden)' if secret else ''),
        ('Environment', settings.LS_CENTRAL_ENVIRONMENT),
        ('Company', settings.LS_CENTRAL_COMPANY or '(only company)'),
        ('API address', f'{settings.LS_CENTRAL_API_URL}/…/{settings.LS_CENTRAL_API_PATH}'),
        ('Invoice statuses imported', ', '.join(settings.LS_CENTRAL_INVOICE_STATUSES)),
        ('Looks back', f'{settings.LS_CENTRAL_SYNC_DAYS} days'),
        ('Automatic sync', f'every {settings.LS_CENTRAL_SYNC_MINUTES:g} minutes'
                           if settings.LS_CENTRAL_SYNC_MINUTES else 'off'),
    ]
    return render(request, 'ls_central/status.html', {
        'rows': rows,
        'missing': missing_settings(),
        'syncs': LsCentralSync.objects.select_related('triggered_by')[:15],
        'imported': LsCentralInvoice.objects.select_related('invoice')[:25],
    })


@login_required
@role_required(*DISPATCH_ROLES)
@require_POST
def sync_now(request):
    run = sync_invoices(user=request.user)
    (messages.success if run.ok else messages.error)(request, f'LS Central: {run.message}')
    return _back(request)


@login_required
@role_required('admin')
@require_POST
def test_connection(request):
    try:
        client = LsCentralClient.from_settings()
        names = [c.get('name', '') for c in client.companies()]
        company_id = client.company_id()
    except LsCentralError as exc:
        messages.error(request, f'Connection failed: {exc}')
    else:
        messages.success(request, f'Connected to LS Central. Companies: {", ".join(names)}. '
                                  f'Using company id {company_id}.')
    return redirect('ls_central:status')
