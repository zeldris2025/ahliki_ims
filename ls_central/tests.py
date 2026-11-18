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
    def __init__(self, docs):
        self.docs = docs

    def sales_invoices(self, since):
        return self.docs


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

    def test_unmatched_and_fractional_lines_are_noted(self):
        lines = [
            {'lineType': 'Item', 'lineObjectNumber': 'NOPE', 'description': 'Mystery', 'quantity': 2, 'unitPrice': 5},
            {'lineType': 'Item', 'lineObjectNumber': 'rice10', 'description': 'Rice', 'quantity': 2.5, 'unitPrice': 50},
            {'lineType': 'Comment', 'description': 'Deliver after 2pm', 'quantity': 0},
        ]
        run = sync_invoices(client=FakeClient([ls_invoice(lines=lines)]))
        self.assertEqual(run.unmatched_lines, 1)
        inv = Invoice.objects.get()
        self.assertEqual(inv.items.get().quantity, 3)   # 2.5 rounded, SKU matched case-insensitively
        note = DispatchComment.objects.get(invoice=inv).body
        self.assertIn('NOPE', note)
        self.assertIn('2.5 → 3', note)

    def test_existing_invoice_number_is_linked_not_duplicated(self):
        Invoice.objects.create(invoice_number='SI-1001', customer_name='Uploaded PDF')
        run = sync_invoices(client=FakeClient([ls_invoice()]))
        self.assertEqual(run.imported, 0)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertTrue(LsCentralInvoice.objects.get().linked_existing)

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
        UserProfile.objects.update_or_create(user=user, defaults={'role': role})
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
