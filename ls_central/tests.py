from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from inventory.models import DispatchComment, Invoice, Product, UserProfile

from .client import LsCentralClient, LsCentralError, NotConfigured
from .models import LsCentralInvoice
from .sync import sync_invoices

KEYS = dict(LS_CENTRAL_TENANT_ID='tenant', LS_CENTRAL_CLIENT_ID='client', LS_CENTRAL_CLIENT_SECRET='secret',
            LS_CENTRAL_ENVIRONMENT='Production', LS_CENTRAL_COMPANY='')


def ls_invoice(number='SI-1001', status='Open', lines=None, **extra):
    doc = {
        'id': f'id-{number}', 'number': number, 'status': status,
        'invoiceDate': timezone.localdate().isoformat(), 'dueDate': '2026-12-01',
        'shortcutDimension1Code': 'HDQ',
        'customerNumber': 'C0042', 'customerName': 'Apia Mini Mart', 'salesperson': 'JS',
        'totalAmountIncludingTax': 230.0, 'totalTaxAmount': 30.0,
        'salesInvoiceLines': lines if lines is not None else [
            {'lineType': 'Item', 'lineObjectNumber': 'RICE10', 'description': 'Rice 10kg',
             'quantity': 4, 'unitPrice': 50.0, 'discountPercent': 0, 'unitOfMeasureCode': 'BAG'},
        ],
    }
    doc.update(extra)
    return doc


class FakeClient:
    def __init__(self, docs, items=None):
        self.docs = docs
        self.items = items or {}
        self.item_calls = []

    def sales_invoices(self, since):
        return [d for d in self.docs if d['invoiceDate'] >= since.isoformat()]

    def sales_invoices_after(self, number):
        return [d for d in self.docs if d['number'] > number]     # compared as text, like LS Central

    def item(self, item_id):
        self.item_calls.append(item_id)
        if item_id not in self.items:
            raise LsCentralError('Not found (404)')
        return self.items[item_id]


@override_settings(**KEYS)
class SyncTests(TestCase):
    def setUp(self):
        self.rice = Product.objects.create(sku='RICE10', name='Rice 10kg', unit_price=Decimal('50'))

    def test_new_invoice_goes_to_dispatch(self):
        run = sync_invoices(client=FakeClient([ls_invoice()]))
        self.assertTrue(run.ok)
        self.assertEqual(run.imported, 1)
        inv = Invoice.objects.get(invoice_number='SI-1001')
        self.assertEqual(inv.dispatch_status, 'pending')
        self.assertEqual(inv.customer_name, 'Apia Mini Mart')
        self.assertEqual(inv.account_number, 'C0042')
        self.assertEqual(inv.total_amount, Decimal('230'))
        item = inv.items.get()
        self.assertEqual((item.product, item.quantity, item.unit_price), (self.rice, 4, Decimal('50')))
        self.assertEqual(inv.ls_central.ls_id, 'id-SI-1001')

    def test_second_sync_does_not_duplicate(self):
        sync_invoices(client=FakeClient([ls_invoice()]))
        run = sync_invoices(client=FakeClient([ls_invoice()]))
        self.assertEqual(run.imported, 0)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_paid_later_updates_status(self):
        sync_invoices(client=FakeClient([ls_invoice()]))
        run = sync_invoices(client=FakeClient([ls_invoice(status='Paid')]))
        self.assertEqual(run.updated, 1)
        self.assertEqual(Invoice.objects.get().status, 'paid')

    def test_drafts_are_skipped_by_default(self):
        sync_invoices(client=FakeClient([ls_invoice(status='Draft')]))
        self.assertFalse(Invoice.objects.exists())

    def test_missing_and_fractional_lines_are_noted(self):
        lines = [
            {'lineType': 'Item', 'lineObjectNumber': 'NOPE', 'description': 'Mystery', 'quantity': 2, 'unitPrice': 5},
            {'lineType': 'Item', 'lineObjectNumber': 'rice10', 'description': 'Rice', 'quantity': 2.5, 'unitPrice': 50},
            {'lineType': 'Item', 'lineObjectNumber': '', 'description': 'No item number', 'quantity': 1},
            {'lineType': 'Comment', 'description': 'Deliver after 2pm', 'quantity': 0},
        ]
        run = sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        self.assertEqual(run.unmatched_lines, 1)        # only the line with no item number
        inv = Invoice.objects.get()
        self.assertEqual(inv.items.get(product=self.rice).quantity, 3)   # 2.5 rounded, SKU matched case-insensitively
        self.assertTrue(inv.items.filter(product__sku='NOPE').exists())   # added to the catalogue
        note = DispatchComment.objects.get(invoice=inv).body
        self.assertIn('NOPE — Mystery', note)
        self.assertIn('No item number', note)
        self.assertIn('2.5 → 3', note)

    def test_matched_by_name_when_item_no_is_not_a_sku(self):
        # Same name, two units of measure: the line's unit picks the right one.
        Product.objects.create(sku='BUTTER-6', name='Anchor Butter 40*227G', unit='6pack', unit_price=Decimal('20'))
        case = Product.objects.create(sku='BUTTER-40', name='Anchor Butter 40*227G', unit='case40',
                                      unit_price=Decimal('130'))
        lines = [{'lineType': 'Item', 'lineObjectNumber': 'AL10000097', 'description': 'Anchor  Butter 40*227G ',
                  'quantity': 2, 'unitPrice': 125, 'unitOfMeasureCode': 'CASE40'}]
        run = sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        self.assertEqual(run.unmatched_lines, 0)
        item = Invoice.objects.get().items.get()
        self.assertEqual((item.product, item.quantity, item.unit_price), (case, 2, Decimal('125')))
        stored = LsCentralInvoice.objects.get().lines
        self.assertEqual((stored[0]['item_no'], stored[0]['sku']), ('AL10000097', 'BUTTER-40'))

    def test_pending_invoice_is_refilled_when_product_appears(self):
        lines = [{'lineType': 'Item', 'lineObjectNumber': '', 'description': 'Sugar 1kg', 'quantity': 3,
                  'unitPrice': 4}]
        sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        inv = Invoice.objects.get()
        self.assertFalse(inv.items.exists())
        self.assertTrue(inv.comments.exists())

        sugar = Product.objects.create(sku='SUGAR1', name='Sugar 1kg', unit_price=Decimal('4'))
        run = sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        self.assertIn('1 pick list filled in', run.message)
        self.assertEqual(inv.items.get().product, sugar)
        self.assertFalse(inv.comments.exists())     # the "no match" note is gone
        self.assertEqual(LsCentralInvoice.objects.get().unmatched_lines, [])

    def test_dispatched_invoice_is_not_rebuilt(self):
        lines = [{'lineType': 'Item', 'lineObjectNumber': '', 'description': 'Sugar 1kg', 'quantity': 3}]
        sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        Invoice.objects.update(dispatch_status='dispatched')
        Product.objects.create(sku='SUGAR1', name='Sugar 1kg', unit_price=Decimal('4'))
        sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        self.assertFalse(Invoice.objects.get().items.exists())

    def test_missing_stock_item_is_added_to_catalogue(self):
        lines = [
            {'lineType': 'Item', 'itemId': 'g-chicken', 'lineObjectNumber': 'AL10003380',
             'description': 'Tanumapua Chicken Whole 2pcs', 'quantity': 3, 'unitPrice': 21.5,
             'unitOfMeasureCode': 'EACH'},
            {'lineType': 'Item', 'itemId': 'g-chicken', 'lineObjectNumber': 'AL10003380',
             'description': 'Tanumapua Chicken Whole 2pcs', 'quantity': 1, 'unitPrice': 21.5,
             'unitOfMeasureCode': 'EACH'},
            {'lineType': 'Item', 'itemId': 'g-sundry', 'lineObjectNumber': 'TRUCK SUNDRY',
             'description': 'FREIGHT', 'quantity': 1, 'unitPrice': 30},
        ]
        client = FakeClient([ls_invoice(lines=lines)], items={
            'g-chicken': {'number': 'AL10003380', 'displayName': 'Tanumapua Chicken Whole 2pcs', 'type': 'Inventory',
                          'baseUnitOfMeasureCode': 'EACH', 'gtin': '9400001', 'unitPrice': 22, 'unitCost': 15},
            'g-sundry': {'number': 'TRUCK SUNDRY', 'displayName': 'Truck sundry', 'type': 'Non-Inventory'},
        })
        run = sync_invoices(client=client)
        self.assertIn('1 product added to the catalogue', run.message)
        self.assertEqual(run.unmatched_lines, 0)
        self.assertEqual(sorted(client.item_calls), ['g-chicken', 'g-sundry'])   # each card read once

        chicken = Product.objects.get(sku='AL10003380')
        self.assertEqual((chicken.name, chicken.unit, chicken.unit_price, chicken.cost_price, chicken.barcode),
                         ('Tanumapua Chicken Whole 2pcs', 'each', Decimal('21.5'), Decimal('15'), '9400001'))
        self.assertFalse(Product.objects.filter(sku='TRUCK SUNDRY').exists())
        inv = Invoice.objects.get()
        self.assertEqual(sorted(inv.items.values_list('quantity', flat=True)), [1, 3])
        self.assertIn('added to Products automatically', inv.comments.get().body)
        self.assertTrue(LsCentralInvoice.objects.get().lines[2]['non_stock'])

    def test_item_card_unreadable_product_made_from_invoice_line(self):
        lines = [{'lineType': 'Item', 'itemId': 'g-x', 'lineObjectNumber': 'AL9', 'description': 'Mystery Box',
                  'quantity': 2, 'unitPrice': 5, 'unitOfMeasureCode': 'CASE12'}]
        run = sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))   # item lookup refused
        self.assertEqual(run.unmatched_lines, 0)
        product = Product.objects.get(sku='AL9')
        self.assertEqual((product.name, product.unit, product.unit_price), ('Mystery Box', 'case12', Decimal('5')))
        self.assertEqual(Invoice.objects.get().items.get().product, product)

    def test_existing_invoice_number_is_linked_not_duplicated(self):
        Invoice.objects.create(invoice_number='SI-1001', customer_name='Uploaded PDF')
        run = sync_invoices(client=FakeClient([ls_invoice()]))
        self.assertEqual(run.imported, 0)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertTrue(LsCentralInvoice.objects.get().linked_existing)
        self.assertEqual(Invoice.objects.get().site, 'HDQ')

    def test_payment_status_is_ignored(self):
        docs = [ls_invoice(number=f'10000{n}', status=status) for n, status in
                enumerate(['Open', 'Paid', ' ', 'Draft', 'In Review', 'Canceled', 'Corrective'])]
        sync_invoices(client=FakeClient(docs))
        self.assertEqual(set(Invoice.objects.values_list('invoice_number', flat=True)),
                         {'100000', '100001', '100002'})

    def test_backdated_invoice_with_a_new_number_is_imported(self):
        current = ls_invoice(number='106230')
        sync_invoices(client=FakeClient([current]))
        docs = [current,
                ls_invoice(number='106231', status='Paid', invoiceDate='2020-01-31'),
                ls_invoice(number='106100', invoiceDate='2020-01-31'),    # history
                ls_invoice(number='99999', invoiceDate='2020-01-31')]     # only newer when compared as text
        run = sync_invoices(client=FakeClient(docs))
        self.assertEqual(run.imported, 1)
        self.assertTrue(Invoice.objects.filter(invoice_number='106231').exists())

    def test_first_sync_does_not_import_history(self):
        sync_invoices(client=FakeClient([ls_invoice(number='106100', invoiceDate='2020-01-31')]))
        self.assertFalse(Invoice.objects.exists())

    def test_connection_error_is_recorded(self):
        class Broken:
            def sales_invoices(self, since):
                raise LsCentralError('Could not reach LS Central: timed out')
        run = sync_invoices(client=Broken())
        self.assertFalse(run.ok)
        self.assertIn('timed out', run.message)


class ConfigTests(TestCase):
    @override_settings(LS_CENTRAL_TENANT_ID='', LS_CENTRAL_CLIENT_ID='', LS_CENTRAL_CLIENT_SECRET='')
    def test_missing_keys_named(self):
        with self.assertRaises(NotConfigured) as ctx:
            LsCentralClient.from_settings()
        self.assertIn('LS_CENTRAL_CLIENT_SECRET', str(ctx.exception))

    @override_settings(**KEYS)
    def test_api_address(self):
        client = LsCentralClient.from_settings()
        self.assertEqual(client.base, 'https://api.businesscentral.dynamics.com/v2.0/tenant/Production/api/v2.0')

    def test_company_picked_by_name(self):
        client = LsCentralClient('t', 'c', 's', 'Production', company='ah liki wholesale')
        with mock.patch.object(client, 'companies', return_value=[
                {'id': 'a', 'name': 'CRONUS'}, {'id': 'b', 'name': 'Ah Liki Wholesale'}]):
            self.assertEqual(client.company_id(), 'b')


@override_settings(**KEYS)
class ViewTests(TestCase):
    def login(self, role):
        user = User.objects.create_user(role, password='pw')
        UserProfile.objects.update_or_create(user=user, defaults={'role': role, 'sites': 'HDQ'})
        self.client.force_login(user)

    def test_dispatcher_sees_bar_and_can_sync(self):
        self.login('wms_dispatcher')
        resp = self.client.get(reverse('warehouse_dispatch_list'))
        self.assertContains(resp, 'LS Central invoices')
        self.assertNotContains(resp, f'href="{reverse("ls_central:status")}"')   # settings link is admin-only
        with mock.patch('ls_central.views.sync_invoices') as sync:
            sync.return_value = mock.Mock(ok=True, message='1 new invoice imported.')
            resp = self.client.post(reverse('ls_central:sync'), {'next': reverse('warehouse_dispatch_list')})
        self.assertRedirects(resp, reverse('warehouse_dispatch_list'), fetch_redirect_response=False)

    def test_status_page_hides_secret_and_is_admin_only(self):
        self.login('wms_dispatcher')
        self.assertNotEqual(self.client.get(reverse('ls_central:status')).status_code, 200)
        self.client.logout()
        self.login('admin')
        resp = self.client.get(reverse('ls_central:status'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, '>secret<')
        self.assertContains(resp, 'set (6 characters, hidden)')

    def test_imported_invoice_pages_render_without_cashier_or_comment_author(self):
        self.login('wms_dispatcher')
        run = sync_invoices(client=FakeClient([ls_invoice(lines=[
            {'lineType': 'Item', 'lineObjectNumber': 'UNKNOWN', 'description': 'Unmatched item',
             'quantity': 2, 'unitPrice': 5},
        ])]))
        self.assertTrue(run.ok)
        invoice = Invoice.objects.get(invoice_number='SI-1001')

        dispatch = self.client.get(reverse('warehouse_dispatch_detail', args=[invoice.pk]))
        self.assertEqual(dispatch.status_code, 200)
        self.assertContains(dispatch, 'Uploaded by</td><td>LS Central')
        self.assertContains(dispatch, 'System')
        self.assertContains(dispatch, 'Unmatched item')

        detail = self.client.get(reverse('invoice_detail', args=[invoice.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Uploaded by</td><td>LS Central')

    def test_imported_invoice_shows_document_and_can_be_dispatched(self):
        self.login('wms_dispatcher')
        sync_invoices(client=FakeClient([ls_invoice(lines=[
            {'lineType': 'Item', 'itemId': 'g-fr', 'lineObjectNumber': 'FREIGHT', 'description': 'Air freight',
             'quantity': 1, 'unitPrice': 30},
            {'lineType': 'Comment', 'description': 'Deliver after 2pm'},
        ])], items={'g-fr': {'number': 'FREIGHT', 'type': 'Service'}}))
        invoice = Invoice.objects.get(invoice_number='SI-1001')
        page = self.client.get(reverse('warehouse_dispatch_detail', args=[invoice.pk]))
        self.assertContains(page, 'Invoice Document')
        self.assertContains(page, 'Air freight')
        self.assertContains(page, 'Non-stock item')
        self.assertContains(page, 'Deliver after 2pm')
        self.assertContains(page, 'Confirm Dispatch')   # nothing to tick, but it can still be cleared
        self.assertFalse(Product.objects.filter(sku='FREIGHT').exists())

        resp = self.client.post(reverse('warehouse_dispatch_submit', args=[invoice.pk]), {'truck_plate': 'S1234'})
        self.assertEqual(resp.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.dispatch_status, 'dispatched')

    def test_process_dispatch_adds_missing_products(self):
        self.login('wms_dispatcher')
        lines = [{'lineType': 'Item', 'lineObjectNumber': 'AL10003380', 'description': 'Tanumapua Chicken Whole 2pcs',
                  'quantity': 3, 'unitPrice': 21.5, 'unitOfMeasureCode': 'EACH'}]
        with mock.patch('ls_central.sync.ProductMatcher.create', return_value=None):
            sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))   # imported while it couldn't be added
        invoice = Invoice.objects.get()
        self.assertFalse(invoice.items.exists())

        with override_settings(LS_CENTRAL_TENANT_ID=''):   # LS Central not reachable from the page
            page = self.client.get(reverse('warehouse_dispatch_detail', args=[invoice.pk]))
        self.assertContains(page, '1 product not in the catalogue added to Products from this invoice: AL10003380')
        self.assertContains(page, 'Order Checklist')
        self.assertContains(page, 'Tanumapua Chicken Whole 2pcs')
        product = Product.objects.get(sku='AL10003380')
        self.assertEqual(invoice.items.get().product, product)
        self.assertEqual(LsCentralInvoice.objects.get().unmatched_lines, [])

        # Opening it again adds nothing more.
        self.client.get(reverse('warehouse_dispatch_detail', args=[invoice.pk]))
        self.assertEqual(Product.objects.filter(sku='AL10003380').count(), 1)

    def _invoice_with_unstocked_item(self):
        Product.objects.create(sku='AL10003380', name='Tanumapua Chicken Whole 2pcs', unit_price=Decimal('6'))
        sync_invoices(client=FakeClient([ls_invoice(lines=[
            {'lineType': 'Item', 'lineObjectNumber': 'AL10003380', 'description': 'Tanumapua Chicken Whole 2pcs',
             'quantity': 3, 'unitPrice': 6}])]))
        return Invoice.objects.get()

    @override_settings(DISPATCH_ALLOW_NO_STOCK=True)
    def test_item_with_no_stock_can_be_dispatched_in_testing_mode(self):
        from inventory.models import StockMovement
        self.login('wms_dispatcher')
        invoice = self._invoice_with_unstocked_item()
        item = invoice.items.get()
        page = self.client.get(reverse('warehouse_dispatch_detail', args=[invoice.pk]))
        self.assertContains(page, 'Testing mode')
        self.assertNotContains(page, 'title="No stock available"')
        self.assertContains(page, f'name="dispatch_qty_{item.pk}"')

        self.client.post(reverse('warehouse_dispatch_submit', args=[invoice.pk]), {
            'truck_plate': 'S1234', 'checked_items': [item.pk], f'dispatch_qty_{item.pk}': 3})
        invoice.refresh_from_db()
        self.assertEqual(invoice.dispatch_status, 'dispatched')
        self.assertEqual(StockMovement.objects.get(product=item.product).quantity, -3)

    @override_settings(DISPATCH_ALLOW_NO_STOCK=False)
    def test_item_with_no_stock_blocks_dispatch_when_testing_mode_is_off(self):
        self.login('wms_dispatcher')
        invoice = self._invoice_with_unstocked_item()
        item = invoice.items.get()
        page = self.client.get(reverse('warehouse_dispatch_detail', args=[invoice.pk]))
        self.assertNotContains(page, 'Testing mode')
        self.assertContains(page, 'title="No stock available"')

        self.client.post(reverse('warehouse_dispatch_submit', args=[invoice.pk]), {
            'truck_plate': 'S1234', 'checked_items': [item.pk], f'dispatch_qty_{item.pk}': 3})
        invoice.refresh_from_db()
        self.assertEqual(invoice.dispatch_status, 'pending')

    def test_long_invoice_is_a_closed_dropdown_above_the_full_checklist(self):
        self.login('wms_dispatcher')
        lines = []
        for n in range(50):
            Product.objects.create(sku=f'P{n}', name=f'Product {n}', unit_price=Decimal('1'))
            lines.append({'lineType': 'Item', 'lineObjectNumber': f'P{n}', 'description': f'Product {n}',
                          'quantity': 1, 'unitPrice': 1})
        sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        invoice = Invoice.objects.get()
        page = self.client.get(reverse('warehouse_dispatch_detail', args=[invoice.pk])).content.decode()
        self.assertIn('<details class="card ls-doc" style="margin-bottom:16px">', page)    # closed
        self.assertIn('50 lines', page)
        self.assertEqual(page.count('class="item-check"'), 50)                         # every row ticked off
        self.assertLess(page.index('Invoice Document'), page.index('Order Checklist'))

        # The Invoice page outside dispatch keeps the document laid out in full.
        detail = self.client.get(reverse('invoice_detail', args=[invoice.pk])).content.decode()
        self.assertNotIn('<details', detail)

    def test_invoice_with_nothing_to_pick_opens_the_dropdown(self):
        self.login('wms_dispatcher')
        sync_invoices(client=FakeClient([ls_invoice(lines=[
            {'lineType': 'Account', 'lineObjectNumber': '12206', 'description': 'Trade promo', 'quantity': 1}])]))
        page = self.client.get(reverse('warehouse_dispatch_detail', args=[Invoice.objects.get().pk]))
        self.assertContains(page, '<details class="card ls-doc" style="margin-bottom:16px" open>')

    def test_invoice_imported_before_lines_were_stored_still_renders(self):
        self.login('wms_dispatcher')
        sync_invoices(client=FakeClient([ls_invoice()]))
        LsCentralInvoice.objects.update(lines=[])
        invoice = Invoice.objects.get()
        for name in ('warehouse_dispatch_detail', 'invoice_detail'):
            resp = self.client.get(reverse(name, args=[invoice.pk]))
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, 'Invoice Document')


class FakeLedgers:
    """The three ledgers for one POS sale, one refund and one back-office invoice."""

    def web_service(self, name, params=None):
        def cle(number, kind, amount):
            return {'Document_No': number, 'Document_Type': kind, 'Amount_LCY': amount,
                    'Customer_No': 'CL1', 'Customer_Name': 'Apia Mini Mart', 'Due_Date': '2026-11-20'}

        def value(entry, number, item, qty, amount):
            return {'Entry_No': entry or 999, 'Item_Ledger_Entry_No': entry, 'Document_No': number,
                    'Item_No': item, 'Item_Description': f'{item} description',
                    'Invoiced_Quantity': qty, 'Sales_Amount_Actual': amount}

        if name == 'Cust_LedgerEntries':
            return [cle('HDQ-HDQ02-14375', 'Invoice', 115), cle('HDQ-HDQ02-14375', 'Payment', -115),
                    cle('SAV-SAV01-200', 'Invoice', 23),
                    cle('SAV-SAV01-201', 'Credit Memo', -23),
                    cle('106230', 'Invoice', 50)]
        return [value(1, 'HDQ-HDQ02-14375', 'AL1', -48, 90),
                value(1, 'HDQ-HDQ02-14375', 'AL1', 0, 0),       # cost adjustment
                value(0, 'HDQ-HDQ02-14375', 'DELIVERY', -1, 10),
                value(2, 'SAV-SAV01-200', 'AL2', -10, 20)]

    def analytics(self, name, params=None):
        return [{'EntryNo': 1, 'UnitOfMeasureCode': 'CASE24', 'QtyPerUnitOfMeasure': 24},
                {'EntryNo': 2, 'UnitOfMeasureCode': 'EACH', 'QtyPerUnitOfMeasure': 1}]


class PosTests(TestCase):
    def docs(self, stores=None):
        from .pos import pos_invoices
        return pos_invoices(FakeLedgers(), timezone.localdate(), stores)

    def test_only_pos_invoices_are_returned(self):
        self.assertEqual([d['number'] for d in self.docs()], ['HDQ-HDQ02-14375', 'SAV-SAV01-200'])
        self.assertEqual([d['number'] for d in self.docs(['sav'])], ['SAV-SAV01-200'])

    def test_invoice_is_rebuilt_from_the_ledgers(self):
        from .pos import save_invoices
        self.assertEqual(save_invoices(self.docs()), 2)
        paid = Invoice.objects.get(invoice_number='HDQ-HDQ02-14375')
        self.assertEqual((paid.status, paid.payment_method, paid.total_amount, paid.tax_amount),
                         ('paid', 'cash', Decimal('115'), Decimal('15')))
        item = paid.items.get()     # the charge is not picked
        self.assertEqual((item.product.sku, item.product.unit, item.quantity, item.unit_price),
                         ('AL1', 'case24', 2, Decimal('45')))
        unpaid = Invoice.objects.get(invoice_number='SAV-SAV01-200')
        self.assertEqual((unpaid.status, unpaid.payment_method), ('unpaid', 'credit'))

    def test_repeat_import_adds_nothing(self):
        from .pos import save_invoices
        save_invoices(self.docs())
        self.assertEqual(save_invoices(self.docs()), 0)
        self.assertEqual(Invoice.objects.count(), 2)

    @override_settings(**KEYS)
    def test_command_only_previews_without_save(self):
        from io import StringIO

        from django.core.management import call_command
        out = StringIO()
        today = timezone.localdate().isoformat()
        with mock.patch.object(LsCentralClient, 'from_settings', return_value=FakeLedgers()):
            call_command('import_pos_invoices', '--from', today, '--to', today, stdout=out)
        self.assertIn('Preview only', out.getvalue())
        self.assertFalse(Invoice.objects.exists())

    def test_pos_numbers_do_not_disturb_the_back_office_sync(self):
        from .pos import save_invoices
        save_invoices(self.docs())
        run = sync_invoices(client=FakeClient([ls_invoice(number='106231')]))
        self.assertTrue(run.ok)
        self.assertEqual(run.imported, 1)

    def test_older_than_five_days_is_refused(self):
        from django.core.management import CommandError, call_command
        too_old = (timezone.localdate() - timezone.timedelta(days=6)).isoformat()
        with self.assertRaisesMessage(CommandError, 'Only the past 5 days'):
            call_command('import_pos_invoices', '--from', too_old)
        self.assertFalse(Invoice.objects.exists())


class StoresAndBackOffice(FakeClient, FakeLedgers):
    """LS Central with back-office invoices and the ledgers. The stores' sales are posted for
    `posted_days` (days before today; 0 is today). Counts the ledger calls."""

    def __init__(self, docs=(), fail=False, posted_days=(0,)):
        super().__init__(list(docs))
        self.ledger_calls, self.fail, self.posted_days = [], fail, posted_days

    def asked_days(self):
        today = timezone.localdate()
        return [(today - timezone.datetime.strptime(f.split(' eq ')[1].split(' ')[0], '%Y-%m-%d').date()).days
                for name, f in self.ledger_calls if name == 'Cust_LedgerEntries' and 'Document_Type' in f]

    def web_service(self, name, params=None):
        if self.fail:
            raise LsCentralError('The app has no permission to read this data (403)')
        where = (params or {}).get('$filter', '')
        self.ledger_calls.append((name, where))
        posted = {(timezone.localdate() - timezone.timedelta(days=n)).isoformat() for n in self.posted_days}
        if not any(day in where for day in posted):
            return []
        rows = super().web_service(name, params)
        if "Document_Type eq 'Invoice'" in where:
            rows = [r for r in rows if r['Document_Type'] == 'Invoice']
        return rows


@override_settings(**KEYS, LS_CENTRAL_IMPORT_POS=True, LS_CENTRAL_POS_MINUTES=30, LS_CENTRAL_SYNC_DAYS=0)
class AutoPosTests(TestCase):
    def test_sync_imports_store_sales_with_back_office_invoices(self):
        run = sync_invoices(client=StoresAndBackOffice([ls_invoice(number='106231')]))
        self.assertTrue(run.ok, run.message)
        self.assertEqual(run.imported, 3)
        self.assertIn('3 new invoices imported (2 from the store tills)', run.message)
        self.assertEqual(sorted(Invoice.objects.values_list('invoice_number', flat=True)),
                         ['106231', 'HDQ-HDQ02-14375', 'SAV-SAV01-200'])

    def test_back_office_invoices_of_today_only(self):
        yesterday = (timezone.localdate() - timezone.timedelta(days=1)).isoformat()
        sync_invoices(client=StoresAndBackOffice([ls_invoice(number='106231'),
                                                  ls_invoice(number='106230', invoiceDate=yesterday)],
                                                 posted_days=()))
        self.assertEqual(list(Invoice.objects.values_list('invoice_number', flat=True)), ['106231'])

    def test_store_sales_of_the_newest_posted_day_only(self):
        client = StoresAndBackOffice(posted_days=(1, 2))      # yesterday's and older sales are posted
        sync_invoices(client=client, force_pos=True)
        self.assertEqual(client.asked_days(), [0, 1])         # stops at yesterday: today's batch
        self.assertEqual(Invoice.objects.count(), 2)

    def test_on_monday_saturdays_sales_are_found(self):
        client = StoresAndBackOffice(posted_days=(2, 3))
        sync_invoices(client=client, force_pos=True)
        self.assertEqual(client.asked_days(), [0, 1, 2])
        self.assertEqual(Invoice.objects.count(), 2)

    def test_looks_back_three_days_at_most(self):
        client = StoresAndBackOffice(posted_days=(4, 5))
        sync_invoices(client=client, force_pos=True)
        self.assertEqual(client.asked_days(), [0, 1, 2, 3])
        self.assertFalse(Invoice.objects.exists())

    def test_light_check_first_full_ledgers_only_when_something_is_new(self):
        client = StoresAndBackOffice()
        sync_invoices(client=client, force_pos=True)
        self.assertEqual([n for n, _ in client.ledger_calls].count('ValueEntries'), 1)
        client.ledger_calls.clear()
        sync_invoices(client=client, force_pos=True)
        self.assertEqual([n for n, _ in client.ledger_calls], ['Cust_LedgerEntries'])
        self.assertEqual(Invoice.objects.count(), 2)

    def test_automatic_sync_checks_the_stores_every_30_minutes(self):
        client = StoresAndBackOffice()
        sync_invoices(client=client)
        self.assertTrue(client.ledger_calls)
        client.ledger_calls.clear()
        sync_invoices(client=client)                      # 10 minutes later
        self.assertEqual(client.ledger_calls, [])
        sync_invoices(client=client, force_pos=True)      # Sync now
        self.assertTrue(client.ledger_calls)

    def test_ledger_errors_do_not_stop_the_back_office_import(self):
        run = sync_invoices(client=StoresAndBackOffice([ls_invoice(number='106231')], fail=True))
        self.assertTrue(run.ok)
        self.assertEqual(run.imported, 1)
        self.assertIn('Store (POS) invoices: The app has no permission', run.message)

    @override_settings(LS_CENTRAL_IMPORT_POS=False)
    def test_can_be_turned_off(self):
        client = StoresAndBackOffice()
        sync_invoices(client=client, force_pos=True)
        self.assertEqual(client.ledger_calls, [])

    def test_sync_now_button_checks_the_stores(self):
        self.client.force_login(User.objects.create_superuser('boss', password='pw'))
        with mock.patch('ls_central.views.sync_invoices') as sync:
            sync.return_value = mock.Mock(ok=True, message='done')
            self.client.post(reverse('ls_central:sync'))
        self.assertTrue(sync.call_args.kwargs['force_pos'])


@override_settings(**KEYS)
class SiteFilterTests(TestCase):
    def setUp(self):
        user = User.objects.create_user('dispatcher', password='pw')
        UserProfile.objects.update_or_create(user=user, defaults={'role': 'admin'})
        self.client.login(username='dispatcher', password='pw')
        for site in ('HDQ', 'SAV', 'TAU', 'VAI', 'CRP', ''):
            for state in ('pending', 'dispatched'):
                invoice = Invoice.objects.create(invoice_number=f'{site or "BLANK"}-{state}', dispatch_status=state,
                                                 site=site)
                LsCentralInvoice.objects.create(invoice=invoice, ls_id=invoice.invoice_number,
                                                ls_number=invoice.invoice_number)
        Invoice.objects.create(invoice_number='UPLOAD-pending', dispatch_status='pending')

    def listed(self, query='', key='pending'):
        page = self.client.get(reverse('warehouse_dispatch_list') + query)
        return sorted(i.invoice_number.rsplit('-', 1)[0] for i in page.context[key])

    def test_each_site(self):
        for site in ('HDQ', 'SAV', 'TAU', 'VAI'):
            self.assertEqual(self.listed(f'?site={site}'), [site])
            self.assertEqual(self.listed(f'?site={site}', 'dispatch_log'), [site])

    def test_several_sites_together(self):
        self.assertEqual(self.listed('?site=&site=HDQ&site=VAI'), ['HDQ', 'VAI'])

    def test_other_catches_unknown_blank_and_uploaded(self):
        self.assertEqual(self.listed('?site=OTHER'), ['BLANK', 'CRP', 'UPLOAD'])
        self.assertEqual(self.listed('?site=OTHER&site=TAU'), ['BLANK', 'CRP', 'TAU', 'UPLOAD'])

    def test_choice_is_remembered_until_all_sites(self):
        self.listed('?site=SAV')
        self.assertEqual(self.listed(), ['SAV'])
        self.assertEqual(len(self.listed('?site=')), 7)
        self.assertEqual(len(self.listed()), 7)

    def test_totals_do_not_shrink_with_the_filter(self):
        options = self.client.get(reverse('warehouse_dispatch_list') + '?site=SAV').context['site_options']
        self.assertEqual([(o['code'], o['pending'], o['dispatched']) for o in options],
                         [('HDQ', 1, 1), ('SAV', 1, 1), ('TAU', 1, 1), ('VAI', 1, 1), ('OTHER', 3, 2)])

    def test_export_follows_the_filter(self):
        body = self.client.get(reverse('warehouse_dispatch_export') + '?site=TAU').content.decode()
        self.assertIn('TAU-dispatched', body)
        self.assertNotIn('HDQ-dispatched', body)

    def test_imports_and_syncs_set_the_site(self):
        doc = ls_invoice(number='106231', shortcutDimension1Code='')
        sync_invoices(client=FakeClient([doc]))
        record = LsCentralInvoice.objects.get(ls_number='106231')
        self.assertEqual(record.invoice.site, '')
        sync_invoices(client=FakeClient([dict(doc, shortcutDimension1Code='SAV')]))    # known: filled in
        record.refresh_from_db()
        self.assertEqual(record.invoice.site, 'SAV')
        sync_invoices(client=FakeClient([ls_invoice(number='106232', shortcutDimension1Code='HDQ')]))
        self.assertEqual(Invoice.objects.get(invoice_number='106232').site, 'HDQ')

    def test_pos_import_sets_the_site(self):
        from .pos import pos_invoices, save_invoices
        save_invoices(pos_invoices(FakeLedgers(), timezone.localdate()))
        self.assertEqual(Invoice.objects.get(invoice_number='SAV-SAV01-200').site, 'SAV')


@override_settings(**KEYS)
class EmptyUserTests(TestCase):
    """LS Central invoices have no cashier, and deleting a user empties cashier and dispatched_by."""

    def test_pages_survive_empty_users(self):
        user = User.objects.create_user('storeman', password='pw')
        UserProfile.objects.update_or_create(user=user, defaults={'role': 'warehouse', 'sites': 'HDQ'})
        self.client.login(username='storeman', password='pw')
        sync_invoices(client=FakeClient([ls_invoice()]))
        Invoice.objects.create(invoice_number='NO-CASHIER', dispatch_status='pending', site='HDQ')
        gone = Invoice.objects.create(invoice_number='NO-DISPATCHER', site='HDQ', dispatch_status='dispatched',
                                      dispatched_at=timezone.now())
        for url in (reverse('dashboard'), reverse('warehouse_dispatch_list'),
                    reverse('warehouse_dispatch_detail', args=[gone.pk]), reverse('invoice_detail', args=[gone.pk])):
            self.assertEqual(self.client.get(url).status_code, 200, url)


class DispatchPagingTests(TestCase):
    def setUp(self):
        user = User.objects.create_user('lead', password='pw')
        UserProfile.objects.update_or_create(user=user, defaults={'role': 'warehouse', 'sites': 'HDQ'})
        self.client.login(username='lead', password='pw')
        now = timezone.now()
        for n in range(65):
            Invoice.objects.create(invoice_number=f'P{n:03}', site='HDQ', customer_name=f'Shop {n}',
                                   created_at=now - timezone.timedelta(minutes=n))
            Invoice.objects.create(invoice_number=f'D{n:03}', site='HDQ', dispatch_status='dispatched',
                                   truck_plate=f'T{n}', dispatched_at=now - timezone.timedelta(days=n))
        Invoice.objects.create(invoice_number='SAV-ONLY', site='SAV')

    def get(self, query=''):
        return self.client.get(reverse('warehouse_dispatch_list') + query)

    def numbers(self, page, key):
        return [i.invoice_number for i in page.context[key]]

    def test_thirty_per_page_on_both_tabs(self):
        page = self.get()
        self.assertEqual(self.numbers(page, 'pending_page'), [f'P{n:03}' for n in range(30)])
        self.assertEqual(len(self.numbers(page, 'log_page')), 30)
        self.assertContains(page, '1–30 of 65')
        self.assertContains(page, '65 pending')
        last = self.get('?page=3&log_page=3')
        self.assertEqual(self.numbers(last, 'pending_page'), [f'P{n:03}' for n in range(60, 65)])
        self.assertEqual(self.numbers(last, 'log_page'), [f'D{n:03}' for n in range(60, 65)])

    def test_pages_cover_every_invoice_once(self):
        seen = []
        for number in (1, 2, 3):
            seen += self.numbers(self.get(f'?page={number}'), 'pending_page')
        self.assertEqual(sorted(seen), [f'P{n:03}' for n in range(65)])

    def test_bad_page_numbers_are_safe(self):
        self.assertEqual(self.numbers(self.get('?page=99'), 'pending_page')[-1], 'P064')
        self.assertEqual(self.numbers(self.get('?page=abc'), 'pending_page')[0], 'P000')

    def test_search_finds_invoices_on_other_pages(self):
        page = self.get('?q=shop 61')
        self.assertEqual(self.numbers(page, 'pending_page'), ['P061'])
        self.assertContains(page, '1 pending')
        log = self.get('?tab=log&lq=T64')
        self.assertEqual(self.numbers(log, 'log_page'), ['D064'])

    def test_dates_filter_the_log(self):
        today = timezone.localdate()
        log = self.get(f'?tab=log&from={today - timezone.timedelta(days=2)}&to={today}')
        self.assertEqual(self.numbers(log, 'log_page'), ['D000', 'D001', 'D002'])

    def test_page_links_keep_searches_tab_and_other_page(self):
        body = self.get('?q=shop&page=2&log_page=2&tab=log&lq=T').content.decode()
        self.assertIn('href="?q=shop&amp;log_page=2&amp;lq=T&page=3"', body)
        self.assertIn('href="?q=shop&amp;page=2&amp;tab=log&amp;lq=T&log_page=3"', body)

    def test_paging_never_shows_another_site(self):
        for number in (1, 2, 3, 4):
            self.assertNotIn('SAV-ONLY', self.numbers(self.get(f'?page={number}&site=SAV'), 'pending_page'))

    def test_query_count_does_not_grow_with_invoices(self):
        self.get()
        with self.assertNumQueries(self._queries()):
            self.get('?page=2')

    def _queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            self.get('?page=1')
        return len(ctx)

    def test_export_still_matches_the_log_search(self):
        body = self.client.get(reverse('warehouse_dispatch_export') + '?q=T64').content.decode()
        self.assertIn('D064', body)
        self.assertNotIn('D063', body)
