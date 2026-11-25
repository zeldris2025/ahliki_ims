"""Phase 4: product catalogue, product profile, stock ledger timeline, stock intelligence, alerts."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (Category, GoodsReceivedNote, GRNItem, Invoice, InvoiceItem, Pallet, Product,
                     StockAlert, StockMovement, Supplier)
from .stock_intel import batch_status, stock_status


def _user(role, sites='HDQ', name=None):
    user = User.objects.create_user(name or f'cat_{role}_{sites}', password='pw')
    user.profile.role = role
    user.profile.sites = sites
    user.profile.save()
    return user


class CatalogueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.food = Category.objects.create(name='Food')
        cls.sup = Supplier.objects.create(name='Island Sun')
        cls.other_sup = Supplier.objects.create(name='Pacific Co')

        def product(sku, stock, reorder=10, cost='2.00', price='5.00', supplier=None, active=True):
            p = Product.objects.create(sku=sku, name=f'Product {sku}', category=cls.food, supplier=supplier or cls.sup,
                                       unit_price=Decimal(price), cost_price=Decimal(cost), reorder_level=reorder,
                                       is_active=active)
            if stock:
                StockMovement.objects.create(product=p, movement_type='in', quantity=stock, reference='GRN-0')
            return p
        cls.healthy = product('AAA', 100, cost='9.00', price='12.00')
        cls.low = product('BBB', 5, supplier=cls.other_sup)
        cls.out = product('CCC', 0)
        cls.retired = product('DDD', 3, active=False)

        today = timezone.localdate()
        grn = GoodsReceivedNote.objects.create(grn_number='GRN-T1', supplier=cls.sup)
        GRNItem.objects.create(grn=grn, product=cls.healthy, quantity_received=20, batch_number='B-SOON',
                               expiry_date=today + timedelta(days=10))
        GRNItem.objects.create(grn=grn, product=cls.low, quantity_received=5, batch_number='B-LATER',
                               expiry_date=today + timedelta(days=200))

        cls.hdq_inv = Invoice.objects.create(invoice_number='HDQ-77', site='HDQ', dispatch_status='dispatched',
                                             dispatched_at=timezone.now())
        cls.sav_inv = Invoice.objects.create(invoice_number='SAV-88', site='SAV', dispatch_status='dispatched',
                                             dispatched_at=timezone.now())
        for inv in (cls.hdq_inv, cls.sav_inv):
            InvoiceItem.objects.create(invoice=inv, product=cls.healthy, quantity=4, unit_price=Decimal('12'))
            StockMovement.objects.create(product=cls.healthy, movement_type='out', quantity=-4,
                                         reference=inv.invoice_number)
        StockMovement.objects.create(product=cls.low, movement_type='adjustment', quantity=-1,
                                     reference='', notes='broken carton')
        Pallet.objects.create(lot_number='LOT-AAA', product=cls.healthy, quantity=20)
        cls.alert = StockAlert.objects.create(product=cls.out, alert_type='low_stock', message='out')
        cls.alert_low = StockAlert.objects.create(product=cls.low, alert_type='low_stock', message='low')

    def login(self, role, sites='HDQ'):
        user = _user(role, sites)
        self.client.force_login(user)
        return user

    # ── rules ────────────────────────────────────────────────────────────────
    def test_status_rules_match_existing_ones(self):
        self.assertEqual([stock_status(s, 10) for s in (-2, 0, 1, 10, 11)],
                         ['out', 'out', 'low', 'low', 'healthy'])
        today = timezone.localdate()
        self.assertEqual(batch_status(today - timedelta(days=1), today), 'expired')
        self.assertEqual(batch_status(today + timedelta(days=30), today), 'expiring')
        self.assertEqual(batch_status(today + timedelta(days=31), today), 'ok')
        self.assertEqual(batch_status(None, today), 'none')

    # ── product list ─────────────────────────────────────────────────────────
    def skus(self, **params):
        r = self.client.get(reverse('product_list'), params)
        self.assertEqual(r.status_code, 200)
        return [row['product'].sku for row in r.context['product_data']]

    def test_sorting_and_bad_sort(self):
        self.login('admin')
        self.assertEqual(self.skus(sort='-stock'), ['AAA', 'BBB', 'CCC'])
        self.assertEqual(self.skus(sort='cost'), ['BBB', 'CCC', 'AAA'])
        self.assertEqual(self.skus(sort='nonsense'), ['AAA', 'BBB', 'CCC'])

    def test_filters(self):
        self.login('admin')
        self.assertEqual(self.skus(stock='expiring'), ['AAA'])
        self.assertEqual(self.skus(supplier=self.other_sup.pk), ['BBB'])
        self.assertEqual(self.skus(active='inactive'), ['DDD'])
        self.assertEqual(len(self.skus(active='all')), 4)
        self.assertEqual(self.skus(q='bbb'), ['BBB'])

    def test_cost_price_hidden_from_cashier(self):
        self.login('cashier')
        r = self.client.get(reverse('product_list'))
        self.assertFalse(r.context['show_cost'])
        self.assertNotContains(r, 'Cost price')
        self.assertFalse(r.context['can_edit'])
        r = self.client.get(reverse('product_detail', args=[self.healthy.pk]))
        self.assertNotContains(r, 'Stock value at cost')

    def test_action_links_follow_roles(self):
        self.login('finance')
        ctx = self.client.get(reverse('product_list')).context
        self.assertEqual((ctx['can_edit'], ctx['can_adjust'], ctx['can_add']), (True, False, False))

    # ── product profile ──────────────────────────────────────────────────────
    def test_product_profile(self):
        self.login('warehouse', 'HDQ')
        r = self.client.get(reverse('product_detail', args=[self.healthy.pk]))
        self.assertEqual(r.status_code, 200)
        ctx = r.context
        self.assertEqual(ctx['current_stock'], 92)
        self.assertEqual(ctx['status'], 'healthy')
        self.assertTrue(ctx['expiring'])
        self.assertEqual(ctx['chart_data']['balance']['datasets'][0]['data'][-1], 92)
        self.assertEqual(len(ctx['pallet_rows']), 1)
        self.assertAlmostEqual(ctx['margin'], 25.0)
        # Dispatches and ledger references only show this user's site.
        self.assertEqual([d.invoice.invoice_number for d in ctx['dispatches']], ['HDQ-77'])
        self.assertNotContains(r, 'SAV-88')
        self.assertContains(r, 'Invoice at another site')

    def test_profile_type_filter(self):
        self.login('admin')
        r = self.client.get(reverse('product_detail', args=[self.healthy.pk]), {'mtype': 'out'})
        self.assertEqual(r.context['moves_page'].paginator.count, 2)

    # ── stock ledger timeline ────────────────────────────────────────────────
    def moves(self, **params):
        r = self.client.get(reverse('stock_movements'), params)
        self.assertEqual(r.status_code, 200)
        return r

    def test_timeline_filters(self):
        self.login('admin')
        self.assertEqual(self.moves(type='adjustment').context['page'].paginator.count, 1)
        self.assertEqual(self.moves(product=self.healthy.pk).context['page'].paginator.count, 3)
        today = timezone.localdate()
        self.assertEqual(self.moves(**{'from': (today + timedelta(days=1)).isoformat()}).context['page'].paginator.count, 0)
        self.assertEqual(self.moves(q='broken').context['page'].paginator.count, 0)   # notes aren't searched
        self.assertEqual(self.moves(q='HDQ-77').context['page'].paginator.count, 1)
        self.assertEqual(self.moves(**{'from': 'junk', 'type': 'junk'}).context['page'].paginator.count, 6)

    def test_reference_search_does_not_reveal_other_sites(self):
        self.login('warehouse', 'HDQ')
        r = self.moves(q='SAV-88')
        self.assertEqual(r.context['page'].paginator.count, 0)
        r = self.moves(product=self.healthy.pk)
        self.assertNotContains(r, 'SAV-88')

    # ── stock intelligence ───────────────────────────────────────────────────
    def test_intelligence_figures(self):
        self.login('manager')
        r = self.client.get(reverse('stock_intelligence'))
        self.assertEqual(r.status_code, 200)
        h = r.context['health']
        self.assertEqual((h['total'], h['healthy'], h['low'], h['out'], h['expiring']), (3, 1, 1, 1, 1))
        self.assertEqual(r.context['totals']['out']['q'], 8)
        self.assertEqual(r.context['rank_out'][0]['product__sku'], 'AAA')
        self.assertEqual(r.context['rank_adjust'][0]['product__sku'], 'BBB')
        self.assertIsNone(r.context['links']['ledger'])     # managers can't open the ledger page

    def test_intelligence_roles(self):
        for role, code in (('admin', 200), ('warehouse', 200), ('manager', 200)):
            self.login(role)
            self.assertEqual(self.client.get(reverse('stock_intelligence')).status_code, code, role)
        for role in ('cashier', 'finance', 'wms_operator', 'custom_broker'):
            self.login(role)
            self.assertEqual(self.client.get(reverse('stock_intelligence')).status_code, 302, role)

    # ── alerts ───────────────────────────────────────────────────────────────
    def test_alert_summary_and_critical_filter(self):
        self.login('warehouse')
        r = self.client.get(reverse('alert_list'))
        s = r.context['summary']
        self.assertEqual((s['outstanding'], s['critical'], s['new'], s['resolved']), (2, 1, 2, 0))
        r = self.client.get(reverse('alert_list'), {'status': 'critical'})
        self.assertEqual([a.pk for a in r.context['alerts']], [self.alert.pk])

    def test_alert_detail(self):
        self.login('warehouse')
        r = self.client.get(reverse('alert_detail', args=[self.alert_low.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['stock'], 4)
        self.assertContains(r, 'Mark resolved')

    def test_resolve_needs_post(self):
        self.login('warehouse')
        url = reverse('alert_resolve', args=[self.alert.pk])
        r = self.client.get(url)
        self.assertRedirects(r, reverse('alert_detail', args=[self.alert.pk]))
        self.alert.refresh_from_db()
        self.assertFalse(self.alert.is_resolved)

        r = self.client.post(url, {'next': reverse('alert_detail', args=[self.alert.pk])})
        self.assertRedirects(r, reverse('alert_detail', args=[self.alert.pk]))
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_resolved)
        self.assertIsNotNone(self.alert.resolved_by)

    def test_resolve_ignores_offsite_next_and_role(self):
        self.login('warehouse')
        r = self.client.post(reverse('alert_resolve', args=[self.alert_low.pk]), {'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('alert_list'))
        self.login('cashier')
        alert = StockAlert.objects.create(product=self.low, alert_type='expiry', message='x')
        self.client.post(reverse('alert_resolve', args=[alert.pk]))
        alert.refresh_from_db()
        self.assertFalse(alert.is_resolved)

    def test_stock_adjust_prefills_product(self):
        self.login('warehouse')
        r = self.client.get(reverse('stock_adjust'), {'product': self.low.pk})
        self.assertEqual(str(r.context['form']['product'].value()), str(self.low.pk))
