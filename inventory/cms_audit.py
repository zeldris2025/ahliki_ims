"""Write entries to the CMS audit log (CmsAuditLog) — who did what, when, and what changed."""
from .models import CmsAuditLog

# Container fields compared on edit / import, with the label shown in the log.
CONTAINER_FIELDS = [
    ('code', 'Code'), ('description', 'Description'), ('yard', 'Yard'), ('status', 'Status'),
    ('owner', 'Owner'), ('vessel_voyage', 'Vessel voyage'), ('arrival_date', 'A/Date'),
    ('driver', 'Driver'), ('note', 'Note'), ('returned', 'Returned'),
]
SHIPPING_FIELDS = [('name', 'Shipping name'), ('return_days', 'Return days')]


def client_ip(request):
    """The browser's address. Azure and other proxies put it first in X-Forwarded-For."""
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    ip = ip.rsplit(':', 1)[0] if ip.count(':') == 1 else ip   # Azure adds the port: 1.2.3.4:5678
    return ip or None


def _display(obj, field):
    value = getattr(obj, field)
    if field == 'status':
        return obj.get_status_display()
    if field == 'returned':
        return 'Yes' if value else 'No'
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    return '' if value is None else str(value)


def snapshot(obj, fields=CONTAINER_FIELDS):
    """The record's current values as text, ready to compare with diff()."""
    return {label: _display(obj, field) for field, label in fields}


def diff(before, after):
    """{label: [old, new]} for every value that changed."""
    return {k: [before.get(k, ''), v] for k, v in after.items() if before.get(k, '') != v}


def record(request, action, summary, obj=None, label='', changes=None, source='', user=None):
    """Add one entry. `request` gives the user and IP address; pass `user` when there is no request."""
    user = user or (request.user if request is not None and request.user.is_authenticated else None)
    return CmsAuditLog.objects.create(
        user_id=user.pk if user else None,
        username=user.get_username() if user else '',
        full_name=(user.get_full_name() if user else '')[:150],
        action=action,
        object_type=obj._meta.model_name if obj is not None else '',
        object_id=obj.pk if obj is not None else None,
        object_label=(label or (str(obj) if obj is not None else ''))[:120],
        summary=summary[:500],
        changes=changes or {},
        source=source[:60],
        ip_address=client_ip(request),
    )
