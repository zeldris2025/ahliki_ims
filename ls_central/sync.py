"""Imports LS Central sales invoices into Warehouse Dispatch.

Each new invoice becomes an Invoice with dispatch status "pending", so it shows up for the WMS
dispatchers exactly like an uploaded one, and they clear it the same way. Item lines are matched
to catalogue products by SKU (LS Central item no.), then barcode. Lines with no match are kept on
the LS Central record and listed in a dispatch comment so nothing goes missing silently.
"""
import logging
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .client import LsCentralClient, LsCentralError
from .models import LsCentralInvoice, LsCentralSync

logger = logging.getLogger(__name__)

# Payment never matters: paid, unpaid and any other posted invoice is imported. These are left out
# because there is nothing to ship yet or any more. (Drafts also have their own number series, which
# repeats the numbers of other, posted invoices.)
NOT_FOR_DISPATCH = {'draft', 'in review', 'canceled', 'corrective'}


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


def _site(doc):
    return str(doc.get('shortcutDimension1Code') or '').strip().upper()[:20]


def _norm(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip().lower()


class ProductMatcher:
    """Finds the catalogue product for an LS Central line.

    LS Central item numbers (e.g. AL10000097) are usually not the catalogue SKUs, so after SKU and
    barcode the line description is matched against product names. Products often exist once per
    unit of measure under the same name (6-pack and case of 24), so ties go to the product whose
    unit matches the line's unit, then to the closest price.

    Lines that still have no match are looked up in LS Central (with `client`): inventory items
    are added to the catalogue, services and non-inventory items (freight, sundries) are not.
    """

    def __init__(self, client=None):
        self._by_name = None
        self.client = client
        self._cards = {}
        self.created = []

    def item_card(self, item_id):
        """The LS Central item card, or None when it can't be read (tried again next sync)."""
        lookup = getattr(self.client, 'item', None)
        if not item_id or not lookup:
            return None
        if item_id not in self._cards:
            try:
                self._cards[item_id] = lookup(item_id) or None
            except LsCentralError as exc:
                logger.warning('LS Central item %s could not be read: %s', item_id, exc)
                self._cards[item_id] = None
        return self._cards[item_id]

    def create(self, row, invoice_number):
        """Add the line's item to the catalogue. Returns the product, or None for non-stock lines.

        Uses the LS Central item card when the app may read it (and skips services / non-inventory
        items such as freight); otherwise the product is made from the invoice line itself.
        """
        from inventory.models import Product
        card = self.item_card(row.get('item_id')) or {}
        if card and str(card.get('type') or 'Inventory') != 'Inventory':
            row['non_stock'] = True
            return None
        sku = str(card.get('number') or row['item_no'] or '').strip()[:100]
        if not sku:
            return None
        existing = Product.objects.filter(sku__iexact=sku).first()
        if existing:
            return existing
        line_price = Decimal(row['unit_price']) if row['unit_price'] else None
        product = Product.objects.create(
            sku=sku,
            name=(row['description'] or card.get('displayName') or sku).strip()[:200],
            unit=(row['unit'] or card.get('baseUnitOfMeasureCode') or 'each').lower()[:50],
            unit_price=line_price if line_price is not None else _decimal(card.get('unitPrice')),
            cost_price=_decimal(card.get('unitCost')),
            barcode=str(card.get('gtin') or '')[:200],
            description=f'Added automatically from LS Central invoice {invoice_number}.',
        )
        self._names()[_norm(product.name)].append(product)
        self.created.append(product)
        return product

    def _names(self):
        if self._by_name is None:
            from inventory.models import Product
            self._by_name = defaultdict(list)
            for product in Product.objects.filter(is_active=True).only('pk', 'name', 'unit', 'unit_price'):
                self._by_name[_norm(product.name)].append(product)
        return self._by_name

    def match(self, item_no, description='', unit='', unit_price=None):
        from inventory.models import Product
        item_no = (item_no or '').strip()
        if item_no:
            product = (Product.objects.filter(sku__iexact=item_no).first()
                       or Product.objects.filter(Q(barcode=item_no) & ~Q(barcode='')).first())
            if product:
                return product
        candidates = self._names().get(_norm(description), [])
        if len(candidates) <= 1:
            return candidates[0] if candidates else None
        same_unit = [p for p in candidates if _norm(p.unit) == _norm(unit)] if unit else []
        candidates = same_unit or candidates
        if unit_price is not None:
            candidates = sorted(candidates, key=lambda p: abs(p.unit_price - unit_price))
        return candidates[0]


def _line_rows(doc):
    """The invoice's lines as plain dicts, in LS Central order, for storing and display."""
    rows = []
    for line in doc.get('salesInvoiceLines') or []:
        qty = _decimal(line.get('quantity'))
        price = _decimal(line.get('unitPrice'))
        discount = _decimal(line.get('discountPercent'))
        amount = line.get('netAmount', line.get('amountExcludingTax'))
        amount = _decimal(amount) if amount is not None else (qty * price * (1 - discount / 100))
        rows.append({
            'line_type': line.get('lineType') or 'Item',
            'item_id': line.get('itemId') or '',
            'item_no': line.get('lineObjectNumber') or line.get('itemNumber') or '',
            'description': line.get('description', ''),
            'quantity': str(qty), 'unit': line.get('unitOfMeasureCode', ''),
            'unit_price': str(price) if line.get('unitPrice') is not None else '', 'discount_percent': str(discount),
            'amount': str(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        })
    return rows


SYSTEM_NOTE_PREFIX = 'LS Central:'


def _build_items(invoice, rows, matcher):
    """Create the pick-list items from the LS Central lines. Returns (rows, unmatched)."""
    from inventory.models import DispatchComment, InvoiceItem

    unmatched, rounded, added = [], [], []
    for row in rows:
        qty = Decimal(row['quantity'])
        if row['line_type'] != 'Item' or qty <= 0:
            continue    # comments, G/L accounts, charges — nothing to pick
        price = Decimal(row['unit_price']) if row['unit_price'] else None
        product = matcher.match(row['item_no'], row['description'], row['unit'], price)
        if not product:
            product = matcher.create(row, invoice.invoice_number)
            if product:
                added.append(product)
        if not product:
            if not row.get('non_stock'):
                unmatched.append({k: row[k] for k in ('item_no', 'description', 'quantity', 'unit')})
            continue
        row['product_id'], row['sku'] = product.pk, product.sku
        whole = int(qty.quantize(Decimal('1'), rounding=ROUND_HALF_UP)) or 1
        if whole != qty:
            rounded.append(f'{product.name}: {qty} → {whole}')
        InvoiceItem.objects.create(invoice=invoice, product=product, quantity=whole,
                                   unit_price=product.unit_price if price is None else price,
                                   discount_percent=Decimal(row['discount_percent']))

    notes = []
    if added:
        notes.append(f'{SYSTEM_NOTE_PREFIX} these items were not in the catalogue and have been added to '
                     'Products automatically. They have no stock in the system yet — receive it before '
                     'they can be ticked off:')
        notes += [f'• {p.sku} — {p.name}' for p in added]
    if unmatched:
        notes.append(f'{SYSTEM_NOTE_PREFIX} these lines have no matching product in the catalogue and '
                     'are not in the pick list — check them against the LS Central invoice:')
        notes += [f'• {u["item_no"] or "(no item no.)"} — {u["description"]} × {u["quantity"]} {u["unit"]}'.rstrip()
                  for u in unmatched]
    if rounded:
        notes.append(f'{SYSTEM_NOTE_PREFIX} part quantities were rounded to whole units:')
        notes += [f'• {r}' for r in rounded]
    if notes:
        DispatchComment.objects.create(invoice=invoice, author=None, body='\n'.join(notes))
    return rows, unmatched


def import_invoice(doc, matcher=None):
    """Create (or link) the Invoice for one LS Central invoice. Returns its LsCentralInvoice."""
    from inventory.models import Invoice

    matcher = matcher or ProductMatcher()
    number = str(doc.get('number') or '').strip()
    if not number:
        raise LsCentralError('An LS Central invoice has no number.')
    ls_status = str(doc.get('status') or '')

    with transaction.atomic():
        existing = Invoice.objects.filter(invoice_number=number).first()
        if existing:
            # LS Central decides the site, whoever uploaded the invoice: its lines are stored with it.
            existing.site = _site(doc)
            existing.save(update_fields=['site'])
            return LsCentralInvoice.objects.create(
                invoice=existing, ls_id=doc['id'], ls_number=number, ls_status=ls_status,
                invoice_date=_date(doc.get('invoiceDate')), linked_existing=True, lines=_line_rows(doc))

        invoice = Invoice.objects.create(
            invoice_number=number,
            cashier=None,
            site=_site(doc),
            customer_name=str(doc.get('customerName') or '')[:200],
            account_number=str(doc.get('customerNumber') or '')[:100],
            payment_method=doc.get('paymentMethod') or ('credit' if doc.get('customerNumber') else 'cash'),
            status='paid' if ls_status == 'Paid' else 'unpaid',
            dispatch_status='pending',
            due_date=_date(doc.get('dueDate')),
            total_amount=_decimal(doc.get('totalAmountIncludingTax')),
            tax_amount=_decimal(doc.get('totalTaxAmount')),
            salesperson=str(doc.get('salesperson') or doc.get('salespersonCode') or '')[:100],
            notes='Imported from LS Central.',
        )

        rows, unmatched = _build_items(invoice, _line_rows(doc), matcher)
        return LsCentralInvoice.objects.create(
            invoice=invoice, ls_id=doc['id'], ls_number=number, ls_status=ls_status,
            invoice_date=_date(doc.get('invoiceDate')), unmatched_lines=unmatched, lines=rows)


def _refresh_lines(record_pk, doc, matcher):
    """Rebuild the pick list of a still-pending imported invoice from the latest LS Central data.

    Picks up products added to the catalogue (or better matching) since the import, and fills in the
    stored lines of invoices imported before they were kept. Returns 1 if the invoice was rebuilt.
    """
    record = LsCentralInvoice.objects.select_related('invoice').get(pk=record_pk)
    if record.linked_existing or record.invoice.dispatch_status != 'pending':
        return 0
    if record.lines and not record.unmatched_lines:
        return 0    # complete already
    return _rebuild(record, _line_rows(doc), matcher)


def _rebuild(record, rows, matcher):
    """Replace the invoice's pick list and system notes with ones built from `rows`. Returns 1 if it changed."""
    invoice = record.invoice
    with transaction.atomic():
        old = sorted(invoice.items.values_list('product_id', 'quantity'))
        invoice.items.all().delete()
        invoice.comments.filter(author=None, body__startswith=SYSTEM_NOTE_PREFIX).delete()
        rows, unmatched = _build_items(invoice, rows, matcher)
        record.lines, record.unmatched_lines = rows, unmatched
        record.save(update_fields=['lines', 'unmatched_lines'])
        return int(sorted(invoice.items.values_list('product_id', 'quantity')) != old)


def complete_pick_list(invoice):
    """Called when a dispatcher opens a pending LS Central invoice: lines that are still not in the
    catalogue are added to Products and put on the pick list. Returns the products added."""
    record = LsCentralInvoice.objects.select_related('invoice').filter(invoice=invoice).first()
    if (not record or record.linked_existing or not record.unmatched_lines or not record.lines
            or record.invoice.dispatch_status != 'pending'):
        return []
    try:
        client = LsCentralClient.from_settings()
    except LsCentralError:
        client = None   # not configured: build from the stored invoice lines alone
    matcher = ProductMatcher(client)
    keep = ('line_type', 'item_id', 'item_no', 'description', 'quantity', 'unit', 'unit_price',
            'discount_percent', 'amount')
    _rebuild(record, [{k: row.get(k, '') for k in keep} for row in record.lines], matcher)
    return matcher.created


def _fetch_invoices(client, since):
    """Invoices dated since `since`, plus any numbered after the newest one imported.

    The second query catches invoices posted now with an old date (e.g. month end), which the date
    filter alone never returns.
    """
    docs = client.sales_invoices(since)
    numbers = [n for n in LsCentralInvoice.objects.values_list('ls_number', flat=True) if n.isdecimal()]
    if not numbers:
        return docs     # first sync: the date window only, not the whole history
    newest = max(numbers, key=int)
    seen = {d.get('id') for d in docs}
    for doc in client.sales_invoices_after(newest):
        number = str(doc.get('number') or '')
        # LS Central compares numbers as text, where '99' comes after '106230'.
        if doc.get('id') not in seen and number.isdecimal() and int(number) > int(newest):
            docs.append(doc)
    return docs


def sync_invoices(user=None, days=None, client=None, force_pos=False):
    """Import new LS Central invoices: back-office ones and store (POS) sales. Always returns the
    LsCentralSync record of the run. `force_pos` checks the stores now, not on their own timer."""
    run = LsCentralSync.objects.create(triggered_by=user if user and user.is_authenticated else None)
    days = settings.LS_CENTRAL_SYNC_DAYS if days is None else days
    errors, rematched, from_stores = [], 0, 0
    try:
        client = client or LsCentralClient.from_settings()
        matcher = ProductMatcher(client)
        docs = _fetch_invoices(client, timezone.localdate() - timedelta(days=days))
        known = dict(LsCentralInvoice.objects.filter(ls_id__in=[d.get('id') for d in docs])
                     .values_list('ls_id', 'pk'))
        for doc in docs:
            if not doc.get('id') or str(doc.get('status', '')).lower() in NOT_FOR_DISPATCH:
                continue
            if doc['id'] in known:
                run.updated += _update_status(known[doc['id']], doc)
                rematched += _refresh_lines(known[doc['id']], doc, matcher)
                continue
            try:
                record = import_invoice(doc, matcher)
            except IntegrityError:
                continue    # imported at the same moment by another worker
            except LsCentralError as exc:
                errors.append(str(exc))
                continue
            if not record.linked_existing:
                run.imported += 1
                run.unmatched_lines += len(record.unmatched_lines)
        if hasattr(client, 'web_service'):      # store sales come from the ledgers
            from .pos import sync_pos
            try:
                from_stores = sync_pos(client, matcher, force=force_pos)
            except LsCentralError as exc:
                errors.append(f'Store (POS) invoices: {exc}')
            run.imported += from_stores
        run.ok = True
        parts = [f'{run.imported} new invoice{"s" if run.imported != 1 else ""} imported'
                 + (f' ({from_stores} from the store tills)' if from_stores else '')]
        if run.updated:
            parts.append(f'{run.updated} marked paid')
        if matcher.created:
            parts.append(f'{len(matcher.created)} product{"s" if len(matcher.created) != 1 else ""} '
                         'added to the catalogue')
        if rematched:
            parts.append(f'{rematched} pick list{"s" if rematched != 1 else ""} filled in from new catalogue matches')
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
    """Keep an imported invoice's payment status and site up to date. Returns 1 if it was marked paid."""
    record = LsCentralInvoice.objects.select_related('invoice').get(pk=record_pk)
    new_status = str(doc.get('status') or '')
    changed = 0
    if new_status == 'Paid' and record.invoice.status == 'unpaid':
        record.invoice.status = 'paid'
        record.invoice.save(update_fields=['status'])
        changed = 1
    site = _site(doc)
    if site and record.invoice.site != site:
        record.invoice.site = site
        record.invoice.save(update_fields=['site'])
    if record.ls_status != new_status:
        record.ls_status = new_status
        record.save(update_fields=['ls_status'])
    return changed
