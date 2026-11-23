from decimal import Decimal

from django import template

from ..client import is_configured
from ..models import LsCentralInvoice, LsCentralSync
from ..views import is_ls_admin

register = template.Library()


@register.inclusion_tag('ls_central/_invoice_document.html')
def ls_invoice_document(invoice, collapsible=False, open=True):
    """The invoice as LS Central sent it, for invoices imported from LS Central (nothing otherwise).

    With `collapsible`, it is drawn as a dropdown with a one-line summary (closed unless `open`),
    so long invoices don't push the dispatch checklist down the page.
    """
    record = LsCentralInvoice.objects.filter(invoice=invoice).first()
    if not record:
        return {'record': None}
    lines = record.lines or []
    for line in lines:
        line['unmatched'] = (not record.linked_existing and line.get('line_type') == 'Item'
                             and 'product_id' not in line and not line.get('non_stock') and Decimal(line.get('quantity') or 0) > 0)
    return {
        'record': record, 'invoice': invoice, 'lines': lines,
        'collapsible': collapsible, 'open': open,
        'line_count': sum(1 for line in lines if line.get('line_type') != 'Comment') or len(record.unmatched_lines or []),
        'subtotal': invoice.total_amount - invoice.tax_amount,
        'unmatched': record.unmatched_lines if not lines else [],
    }


@register.inclusion_tag('ls_central/_dispatch_bar.html', takes_context=True)
def ls_central_bar(context):
    """Sync button and last-sync line for the Warehouse Dispatch page."""
    request = context.get('request')
    return {
        'configured': is_configured(),
        'last': LsCentralSync.objects.first(),
        'request': request,
        'csrf_token': context.get('csrf_token'),
        'can_configure': bool(request) and is_ls_admin(request.user),
    }
