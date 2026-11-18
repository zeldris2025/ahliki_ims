"""Imports LS Central sales invoices into Warehouse Dispatch.

Each new invoice becomes an Invoice with dispatch status "pending", so it shows up for the WMS
dispatchers exactly like an uploaded one, and they clear it the same way. Item lines are matched
to catalogue products by SKU (LS Central item no.), then barcode. Lines with no match are kept on
the LS Central record and listed in a dispatch comment so nothing goes missing silently.
"""
import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .client import LsCentralClient, LsCentralError
from .models import LsCentralInvoice, LsCentralSync

logger = logging.getLogger(__name__)


def _decimal(value, default='0'):
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _find_product(item_no):
    from inventory.models import Product
    item_no = (item_no or '').strip()
    if not item_no:
        return None
    return (Product.objects.filter(sku__iexact=item_no).first()
            or Product.objects.filter(Q(barcode=item_no) & ~Q(barcode='')).first())


def import_invoice(doc):
    """Create (or link) the Invoice for one LS Central invoice. Returns its LsCentralInvoice."""
    from inventory.models import DispatchComment, Invoice, InvoiceItem

    number = str(doc.get('number') or '').strip()
    if not number:
        raise LsCentralError('An LS Central invoice has no number.')
    ls_status = str(doc.get('status') or '')

    with transaction.atomic():
        existing = Invoice.objects.filter(invoice_number=number).first()
        if existing:
            return LsCentralInvoice.objects.create(
                invoice=existing, ls_id=doc['id'], ls_number=number, ls_status=ls_status,
                invoice_date=_date(doc.get('invoiceDate')), linked_existing=True)

        invoice = Invoice.objects.create(
            invoice_number=number,
            cashier=None,
            customer_name=str(doc.get('customerName') or '')[:200],
            account_number=str(doc.get('customerNumber') or '')[:100],
            payment_method='credit' if doc.get('customerNumber') else 'cash',
            status='paid' if ls_status == 'Paid' else 'unpaid',
            dispatch_status='pending',
            due_date=_date(doc.get('dueDate')),
            total_amount=_decimal(doc.get('totalAmountIncludingTax')),
            tax_amount=_decimal(doc.get('totalTaxAmount')),
            salesperson=str(doc.get('salesperson') or doc.get('salespersonCode') or '')[:100],
            notes='Imported from LS Central.',
        )

        unmatched, rounded = [], []
        for line in doc.get('salesInvoiceLines') or []:
            if line.get('lineType') not in ('Item', None):
                continue    # comments, G/L accounts, charges — nothing to pick
            qty = _decimal(line.get('quantity'))
            if qty <= 0:
                continue
            item_no = line.get('lineObjectNumber') or line.get('itemNumber') or ''
            product = _find_product(item_no)
            if not product:
                unmatched.append({'item_no': item_no, 'description': line.get('description', ''),
                                  'quantity': str(qty), 'unit': line.get('unitOfMeasureCode', '')})
                continue
            whole = int(qty.quantize(Decimal('1'), rounding=ROUND_HALF_UP)) or 1
            if whole != qty:
                rounded.append(f'{product.name}: {qty} → {whole}')
            InvoiceItem.objects.create(
                invoice=invoice, product=product, quantity=whole,
                unit_price=_decimal(line.get('unitPrice'), product.unit_price),
                discount_percent=_decimal(line.get('discountPercent')),
            )

        notes = []
        if unmatched:
            notes.append('LS Central: these lines have no matching product (SKU) in the catalogue and '
                         'are not in the pick list — check them against the LS Central invoice:')
            notes += [f'• {u["item_no"] or "(no item no.)"} — {u["description"]} × {u["quantity"]} {u["unit"]}'.rstrip()
                      for u in unmatched]
        if rounded:
            notes.append('LS Central: part quantities were rounded to whole units:')
            notes += [f'• {r}' for r in rounded]
        if notes:
            DispatchComment.objects.create(invoice=invoice, author=None, body='\n'.join(notes))

        return LsCentralInvoice.objects.create(
            invoice=invoice, ls_id=doc['id'], ls_number=number, ls_status=ls_status,
            invoice_date=_date(doc.get('invoiceDate')), unmatched_lines=unmatched)


def sync_invoices(user=None, days=None, client=None):
    """Import new LS Central invoices. Always returns the LsCentralSync record of the run."""
    run = LsCentralSync.objects.create(triggered_by=user if user and user.is_authenticated else None)
    statuses = {s.strip().lower() for s in settings.LS_CENTRAL_INVOICE_STATUSES}
    days = settings.LS_CENTRAL_SYNC_DAYS if days is None else days
    errors = []
    try:
        client = client or LsCentralClient.from_settings()
        docs = client.sales_invoices(timezone.localdate() - timedelta(days=days))
        known = dict(LsCentralInvoice.objects.filter(ls_id__in=[d.get('id') for d in docs])
                     .values_list('ls_id', 'pk'))
        for doc in docs:
            if not doc.get('id') or str(doc.get('status', '')).lower() not in statuses:
                continue
            if doc['id'] in known:
                run.updated += _update_status(known[doc['id']], doc)
                continue
            try:
                record = import_invoice(doc)
            except IntegrityError:
                continue    # imported at the same moment by another worker
            except LsCentralError as exc:
                errors.append(str(exc))
                continue
            if not record.linked_existing:
                run.imported += 1
                run.unmatched_lines += len(record.unmatched_lines)
        run.ok = True
        parts = [f'{run.imported} new invoice{"s" if run.imported != 1 else ""} imported']
        if run.updated:
            parts.append(f'{run.updated} marked paid')
        if run.unmatched_lines:
            parts.append(f'{run.unmatched_lines} line{"s" if run.unmatched_lines != 1 else ""} '
                         'without a catalogue match')
        run.message = ', '.join(parts) + '.' + (' ' + ' '.join(errors) if errors else '')
    except LsCentralError as exc:
        run.message = str(exc)
    except Exception as exc:   # keep a record of unexpected failures too
        logger.exception('LS Central sync failed')
        run.message = f'Unexpected error: {exc}'
    run.finished_at = timezone.now()
    run.save()
    return run


def _update_status(record_pk, doc):
    """Mark an imported invoice paid once LS Central says it is. Returns 1 if it changed."""
    record = LsCentralInvoice.objects.select_related('invoice').get(pk=record_pk)
    new_status = str(doc.get('status') or '')
    changed = 0
    if new_status == 'Paid' and record.invoice.status == 'unpaid':
        record.invoice.status = 'paid'
        record.invoice.save(update_fields=['status'])
        changed = 1
    if record.ls_status != new_status:
        record.ls_status = new_status
        record.save(update_fields=['ls_status'])
    return changed
