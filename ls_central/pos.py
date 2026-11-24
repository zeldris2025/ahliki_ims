"""POS invoices (HDQ-HDQ02-14375 and the like), rebuilt from the LS Central ledgers.

The salesInvoices API has only back-office invoices. Store sales reach the ledgers when the store
statements are posted, normally the next working morning, so they are not live. Three ledgers, all
readable with the app's normal permissions, make up one invoice:

* Customer ledger: the invoice number, customer, total and whether it was paid at the till.
* Value entries: the items, their descriptions and amounts (excluding VAGST).
* Item ledger: the unit of measure sold (quantities there are in the base unit).

Refunds are credit memos in the ledger and are not imported.

The automatic sync (sync_pos) imports today's batch: the newest day the stores have posted. It
first asks only for the day's invoice numbers, which is quick, and reads the ledgers in full only
when some are not imported yet. import_pos_invoices fetches older days (past MAX_DAYS at most).
"""
import re
from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Max
from django.utils import timezone

from .models import LsCentralInvoice, LsCentralPosDay
from .sync import ProductMatcher, _decimal, import_invoice

MAX_DAYS = 5    # how far back POS invoices may be imported; the full history is over 330,000 invoices
# How far back the automatic sync looks for the newest posted day (Saturday's sales, on a Monday).
LOOK_BACK_DAYS = 3
POS_NUMBER = re.compile(r'^([A-Z]{3})-\1\d+-\d+$')


def store_of(number):
    """'HDQ' for HDQ-HDQ02-14375, or None when it is not a POS number."""
    found = POS_NUMBER.match(str(number or ''))
    return found.group(1) if found else None


def pos_invoices(client, day, stores=None):
    """The POS invoices posted on `day`, shaped like the salesInvoices API's documents."""
    stores = {s.upper() for s in stores or ()}

    def wanted(number):
        store = store_of(number)
        return store is not None and (not stores or store in stores)

    totals, paid = defaultdict(Decimal), defaultdict(Decimal)
    headers = {}
    for row in client.web_service('Cust_LedgerEntries', {'$filter': f'Posting_Date eq {day.isoformat()}'}):
        number = row.get('Document_No')
        if not wanted(number):
            continue
        if row.get('Document_Type') == 'Invoice':
            headers.setdefault(number, row)
            totals[number] += _decimal(row.get('Amount_LCY'))
        elif row.get('Document_Type') == 'Payment':
            paid[number] -= _decimal(row.get('Amount_LCY'))
    if not headers:
        return []

    units = {row['EntryNo']: row for row in client.analytics(
        'itemLedgerEntries', {'$filter': f'PostingDate eq {day.isoformat()}'})}

    # One sold line can have several value entries (cost adjustments): add them up.
    lines = defaultdict(dict)
    for row in client.web_service('ValueEntries', {'$filter': f'Posting_Date eq {day.isoformat()}'}):
        number = row.get('Document_No')
        if number not in headers:
            continue
        entry = row.get('Item_Ledger_Entry_No')
        key = ('item', entry) if entry else ('charge', row.get('Entry_No'))
        line = lines[number].setdefault(key, {'entry': entry, 'item_no': row.get('Item_No') or '',
                                              'description': '', 'quantity': Decimal(0), 'amount': Decimal(0)})
        line['description'] = line['description'] or row.get('Item_Description') or ''
        line['quantity'] -= _decimal(row.get('Invoiced_Quantity'))
        line['amount'] += _decimal(row.get('Sales_Amount_Actual'))

    return [_document(number, day, headers[number], totals[number], paid[number],
                      lines[number].values(), units)
            for number in sorted(headers)]


def _document(number, day, header, total, paid, lines, units):
    doc_lines, net = [], Decimal(0)
    for line in lines:
        qty, amount = line['quantity'], line['amount']
        net += amount
        if not qty and not amount:
            continue
        unit = units.get(line['entry'], {})
        qty = qty / (_decimal(unit.get('QtyPerUnitOfMeasure'), '1') or Decimal(1))
        qty = qty.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP).normalize()
        price = (amount / qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if qty else None
        doc_lines.append({
            'lineType': 'Item' if line['entry'] else 'Charge',     # no item ledger entry: nothing to pick
            'lineObjectNumber': line['item_no'],
            'description': line['description'] or line['item_no'],
            'quantity': format(qty, 'f'),
            'unitOfMeasureCode': unit.get('UnitOfMeasureCode', ''),
            'unitPrice': price,
            'netAmount': amount,
        })
    settled = paid >= total
    return {
        'id': f'POS:{number}',
        'number': number,
        'status': 'Paid' if settled else 'Open',
        'invoiceDate': day.isoformat(),
        'shortcutDimension1Code': store_of(number),
        'dueDate': header.get('Due_Date'),
        'customerNumber': header.get('Customer_No'),
        'customerName': header.get('Customer_Name'),
        # Till sales are posted against a customer too, so a customer number doesn't mean credit.
        'paymentMethod': 'cash' if settled else 'credit',
        'totalAmountIncludingTax': total,
        'totalTaxAmount': total - net,
        'salesInvoiceLines': doc_lines,
    }


def not_yet_imported(docs):
    ids = [d['id'] for d in docs]
    known = set()
    for start in range(0, len(ids), 500):
        known.update(LsCentralInvoice.objects.filter(ls_id__in=ids[start:start + 500])
                     .values_list('ls_id', flat=True))
    return [d for d in docs if d['id'] not in known]


def save_invoices(docs, matcher=None):
    """Put POS invoices into Pending Dispatch. Safe to repeat. Returns how many were added."""
    matcher = matcher or ProductMatcher()
    added = 0
    for doc in not_yet_imported(docs):
        try:
            record = import_invoice(doc, matcher)
        except IntegrityError:
            continue    # imported at the same moment by someone else
        added += not record.linked_existing
    return added


def posted_numbers(client, day):
    """The POS invoice numbers LS Central has for `day`: one light query on the customer ledger."""
    rows = client.web_service('Cust_LedgerEntries', {
        '$filter': f"Posting_Date eq {day.isoformat()} and Document_Type eq 'Invoice'",
        '$select': 'Document_No,Document_Type'})
    return {r['Document_No'] for r in rows
            if r.get('Document_Type', 'Invoice') == 'Invoice' and store_of(r.get('Document_No'))}


def _imported(numbers):
    ids = [f'POS:{n}' for n in numbers]
    return sum(LsCentralInvoice.objects.filter(ls_id__in=ids[i:i + 500]).count() for i in range(0, len(ids), 500))


def sync_pos(client, matcher=None, force=False):
    """Import today's batch of store sales: the newest day the stores have posted. Returns how many.

    Sales are posted the next working morning, so that is yesterday, or Saturday on a Monday. Only
    the days since are asked (a light query each); older days are left to import_pos_invoices.
    Runs at most every LS_CENTRAL_POS_MINUTES unless `force` (Sync now).
    """
    if not settings.LS_CENTRAL_IMPORT_POS:
        return 0
    now = timezone.now()
    last = LsCentralPosDay.objects.aggregate(last=Max('checked_at'))['last']
    if not force and last and now - last < timedelta(minutes=settings.LS_CENTRAL_POS_MINUTES):
        return 0
    today = timezone.localdate()
    LsCentralPosDay.objects.filter(day__lt=today - timedelta(days=MAX_DAYS)).delete()
    added = 0
    for back in range(LOOK_BACK_DAYS + 1):
        day = today - timedelta(days=back)
        numbers = posted_numbers(client, day)
        imported = _imported(numbers)
        if imported < len(numbers):
            added += save_invoices(pos_invoices(client, day), matcher or ProductMatcher())
            imported = _imported(numbers)
        LsCentralPosDay.objects.update_or_create(day=day, defaults={
            'posted': len(numbers), 'imported': imported, 'checked_at': now,
            'complete': imported >= len(numbers)})
        if numbers:
            break       # the newest posted day: today's batch
    return added
