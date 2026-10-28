"""Audit trail — records who created, changed or deleted what, and every sign-in.

AuditMiddleware remembers the current request so the model signals below know
who is acting. Saves made outside a web request (background tracking refresh,
management commands, migrations) are not people's actions and are not logged.
"""
from contextvars import ContextVar

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save

_current_request = ContextVar('audit_request', default=None)

# Which area of the system each model belongs to (see AuditLog.AREA_CHOICES).
MODEL_AREAS = {
    'Product': 'products', 'Category': 'products', 'Supplier': 'products',
    'PurchaseOrder': 'warehouse', 'PurchaseOrderItem': 'warehouse',
    'GoodsReceivedNote': 'warehouse', 'GRNItem': 'warehouse',
    'StockMovement': 'warehouse', 'StockAlert': 'warehouse', 'DispatchComment': 'warehouse',
    'Container': 'warehouse', 'ContainerItem': 'warehouse', 'ContainerComment': 'warehouse',
    'ContainerType': 'warehouse', 'ShipmentTracking': 'warehouse',
    'ShelfLocation': 'wms', 'Pallet': 'wms', 'PalletLocation': 'wms',
    'Yard': 'containers', 'ShippingLine': 'containers', 'CmsContainer': 'containers',
    'ContainerReturn': 'containers', 'ContainerTransfer': 'containers',
    'Sale': 'sales', 'SaleItem': 'sales', 'Quote': 'sales', 'QuoteItem': 'sales',
    'Invoice': 'sales', 'InvoiceItem': 'sales',
    'User': 'users', 'UserProfile': 'users',
}

# Fields that change on their own and would only add noise.
IGNORED_FIELDS = {'last_login'}
# Fields whose values must never be written to the log.
SECRET_FIELDS = {'password'}


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    # Azure App Service appends the client port to IPv4 addresses ("1.2.3.4:5678").
    if ip.count(':') == 1:
        ip = ip.split(':')[0]
    return ip


def department_for(user):
    from .models import UserProfile
    if not user or not user.is_authenticated:
        return '', 'system'
    profile = UserProfile.objects.filter(user=user).only('role').first()
    role = profile.role if profile else ''
    if user.is_superuser:
        return role, 'management'
    return role, UserProfile.ROLE_DEPARTMENTS.get(role, 'system')


def write_log(action, *, request=None, user=None, instance=None, changes=None, username=''):
    from .models import AuditLog
    if user is None and request is not None and getattr(request, 'user', None) is not None:
        user = request.user if request.user.is_authenticated else None
    role, department = department_for(user)
    entry = AuditLog(
        user=user,
        username=user.get_username() if user else username,
        role=role,
        department=department,
        action=action,
        changes=changes or {},
    )
    if request is not None:
        entry.ip_address = client_ip(request)[:64]
        entry.path = request.path[:255]
    if instance is not None:
        name = type(instance).__name__
        entry.area = MODEL_AREAS.get(name, 'other')
        entry.object_type = str(instance._meta.verbose_name).capitalize()[:100]
        entry.object_id = str(instance.pk)[:64]
        try:
            entry.object_repr = str(instance)[:255]
        except Exception:
            entry.object_repr = f'#{instance.pk}'
    elif action in ('login', 'logout', 'login_failed'):
        entry.area = 'users'
    entry.save()
    return entry


# ── Model changes ──────────────────────────────────────────────────────────────

def _tracked_fields(instance):
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in IGNORED_FIELDS:
            continue
        if getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False):
            continue
        yield field


def _display(field, value):
    if value is None or value == '':
        return ''
    if field.name in SECRET_FIELDS:
        return '••••••'
    if field.is_relation:
        try:
            return str(field.related_model._default_manager.get(pk=value))
        except Exception:
            return f'#{value}'
    if field.choices:
        return str(dict(field.flatchoices).get(value, value))
    if hasattr(value, 'name'):  # uploaded file
        return value.name or ''
    return str(value)


def _snapshot(instance):
    return {f.name: f.value_from_object(instance) for f in _tracked_fields(instance)}


def _should_log(sender, raw=False):
    from .models import AuditLog
    if raw or sender is AuditLog or _current_request.get() is None:
        return False
    return sender._meta.app_label == 'inventory' or sender is get_user_model()


def on_pre_save(sender, instance, raw=False, **kwargs):
    if not _should_log(sender, raw) or instance._state.adding or instance.pk is None:
        return
    old = sender._default_manager.filter(pk=instance.pk).first()
    instance._audit_before = _snapshot(old) if old else None


def on_post_save(sender, instance, created, raw=False, **kwargs):
    if not _should_log(sender, raw):
        return
    fields = {f.name: f for f in _tracked_fields(instance)}
    after = _snapshot(instance)
    if created:
        changes = {name: ['', _display(fields[name], value)]
                   for name, value in after.items() if value not in (None, '')}
        write_log('create', request=_current_request.get(), instance=instance, changes=changes)
        return
    before = getattr(instance, '_audit_before', None)
    instance._audit_before = None
    if before is None:
        return
    changes = {name: [_display(fields[name], before[name]), _display(fields[name], value)]
               for name, value in after.items() if before.get(name) != value}
    if changes:
        write_log('update', request=_current_request.get(), instance=instance, changes=changes)


def on_post_delete(sender, instance, **kwargs):
    if not _should_log(sender):
        return
    fields = {f.name: f for f in _tracked_fields(instance)}
    changes = {name: [_display(fields[name], value), '']
               for name, value in _snapshot(instance).items() if value not in (None, '')}
    write_log('delete', request=_current_request.get(), instance=instance, changes=changes)


# ── Sign-ins ───────────────────────────────────────────────────────────────────

def on_logged_in(sender, request, user, **kwargs):
    write_log('login', request=request, user=user)


def on_logged_out(sender, request, user, **kwargs):
    if user is not None:
        write_log('logout', request=request, user=user)


def on_login_failed(sender, credentials, request=None, **kwargs):
    write_log('login_failed', request=request,
              username=str(credentials.get('username', ''))[:150])


def connect():
    pre_save.connect(on_pre_save, dispatch_uid='audit_pre_save')
    post_save.connect(on_post_save, dispatch_uid='audit_post_save')
    post_delete.connect(on_post_delete, dispatch_uid='audit_post_delete')
    user_logged_in.connect(on_logged_in, dispatch_uid='audit_logged_in')
    user_logged_out.connect(on_logged_out, dispatch_uid='audit_logged_out')
    user_login_failed.connect(on_login_failed, dispatch_uid='audit_login_failed')
