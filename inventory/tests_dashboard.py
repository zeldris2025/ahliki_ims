"""Executive dashboard: real figures, role-aware sections, site-checked dispatch numbers."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (Category, Container, Invoice, Pallet, PalletLocation, Product, ShelfLocation,
                     StockAlert, StockMovement, Supplier)


def _user(role, sites='HDQ'):
    user = User.objects.create_user(f'dash_{role}_{sites}', password='pw')
    user.profile.role = role
    user.profile.sites = sites
    user.profile.save()
    return user


class DashboardFiguresTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.food = Category.objects.create(name='Food')
        cls.drink = Category.objects.create(name='Drink')
        sup = Supplier.objects.create(name='Island Sun')

        def product(sku, cat, stock, reorder=10, cost='2.00'):
            p = Product.objects.create(sku=sku, name=sku, category=cat, supplier=sup, unit_price=Decimal('5'),
                                       cost_price=Decimal(cost), reorder_level=reorder)
            if stock:
                StockMovement.objects.create(product=p, movement_type='in', quantity=stock, reference='GRN-1')
            return p
        cls.healthy = product('HEALTHY', cls.food, 100)
        cls.low = product('LOW', cls.food, 5)
        cls.out = product('OUT', cls.drink, 0)
        StockMovement.objects.create(product=cls.healthy, movement_type='out', quantity=-30, reference='INV-1')

        now = timezone.now()
        Invoice.objects.create(invoice_number='HDQ-1', site='HDQ', created_at=now)
        Invoice.objects.create(invoice_number='HDQ-OLD', site='HDQ', created_at=now - timedelta(days=3))
        Invoice.objects.create(invoice_number='SAV-1', site='SAV', created_at=now)
        Invoice.objects.create(invoice_number='HDQ-DONE', site='HDQ', dispatch_status='dispatched', dispatched_at=now)

        Container.objects.create(container_number='MSKU1234567', status=Container.STATUS_AT_WHARF)
        Container.objects.create(container_number='MSKU7654321', status=Container.STATUS_CLOSED)
        shelf = ShelfLocation.objects.create(code='QQ1', letter='QQ', story=1)
        on_shelf = Pallet.objects.create(lot_number='LOT-1', product=cls.healthy, quantity=10)
        Pallet.objects.create(lot_number='LOT-2', product=cls.healthy, quantity=10)
        PalletLocation.objects.create(pallet=on_shelf, shelf=shelf)
        StockAlert.objects.create(product=cls.low, alert_type='low_stock', message='low')

    def get(self, role, sites='HDQ', **params):
        self.client.force_login(_user(role, sites))
        return self.client.get(reverse('dashboard'), params)

    def test_admin_figures_come_from_the_ledger(self):
        ctx = self.get('admin').context
        inv = ctx['inventory']
        self.assertEqual((inv['total'], inv['units'], inv['low_only'], inv['out'], inv['healthy']), (3, 75, 1, 1, 1))
        self.assertEqual(ctx['value']['total'], Decimal('150.00'))      # 75 units × 2.00
        ops = ctx['operations']
        self.assertEqual((ops['active'], ops['awaiting_receipt']), (1, 1))
        self.assertEqual((ops['pallets'], ops['shelved'], ops['unshelved']), (2, 1, 1))
        shelves = ShelfLocation.objects.count()     # migrations seed the standard shelves
        self.assertEqual((ops['shelves'], ops['occupied'], ops['available']), (shelves, 1, shelves - 1))
        self.assertEqual(ctx['alerts']['open'], 1)
        self.assertEqual(ctx['movement']['totals']['out']['q'], 30)

    def test_category_filter(self):
        inv = self.get('admin', category=self.drink.pk).context['inventory']
        self.assertEqual((inv['total'], inv['units'], inv['out']), (1, 0, 1))

    def test_dispatch_counts_only_visible_sites(self):
        d = self.get('warehouse', 'HDQ').context['dispatch']
        self.assertEqual((d['pending'], d['pending_today'], d['dispatched_today']), (2, 1, 1))
        self.assertEqual(d['sites']['labels'], ['HDQ'])

    def test_site_param_outside_own_sites_is_ignored(self):
        ctx = self.get('warehouse', 'HDQ', site='SAV').context
        self.assertEqual(ctx['filters'].site, '')
        self.assertEqual(ctx['dispatch']['pending'], 2)
        self.assertNotContains(self.client.get(reverse('dashboard'), {'site': 'SAV'}), 'SAV-1')

    def test_admin_site_filter(self):
        d = self.get('admin', site='SAV').context['dispatch']
        self.assertEqual(d['pending'], 1)

    def test_sections_follow_role(self):
        expected = {
            'admin': {'value', 'movement', 'operations', 'dispatch', 'alerts'},
            'finance': {'value', 'movement', 'alerts'},
            'cashier': set(),
        }
        for role, sections in expected.items():
            with self.subTest(role=role):
                ctx = self.get(role, 'HDQ').context
                self.assertEqual({k for k, v in ctx['show'].items() if v and k != 'inventory'}, sections)
                self.assertTrue(all(k not in ctx for k in {'dispatch', 'operations', 'value'} - sections))
                self.client.logout()

    def test_kpi_links_only_point_at_permitted_pages(self):
        for role in ('admin', 'manager', 'finance', 'warehouse', 'cashier'):
            with self.subTest(role=role):
                response = self.get(role, 'HDQ')
                self.assertEqual(response.status_code, 200)
                for k in response.context['kpis']:
                    if k['href']:
                        self.assertEqual(self.client.get(k['href']).status_code, 200, f"{role}: {k['label']} → {k['href']}")
                self.client.logout()

    def test_low_stock_link_lists_the_same_products(self):
        self.get('admin')
        response = self.client.get(reverse('product_list'), {'stock': 'low'})
        self.assertEqual([r['product'].sku for r in response.context['product_data']], ['LOW'])
        response = self.client.get(reverse('product_list'), {'stock': 'out'})
        self.assertEqual([r['product'].sku for r in response.context['product_data']], ['OUT'])

    def test_bad_filters_fall_back_to_defaults(self):
        ctx = self.get('admin', range='nonsense', category='x', **{'from': 'bad'}).context
        self.assertEqual((ctx['filters'].range_key, ctx['filters'].days, ctx['filters'].category), ('30', 30, None))

    def test_custom_range(self):
        today = timezone.localdate()
        ctx = self.get('admin', range='custom', **{'from': (today - timedelta(days=6)).isoformat(),
                                                    'to': today.isoformat()}).context
        self.assertEqual(ctx['filters'].days, 7)
        self.assertEqual(len(ctx['chart_data']['movement']['labels']), 7)


class ListFilterTests(TestCase):
    def setUp(self):
        self.client.force_login(_user('admin'))
        p = Product.objects.create(sku='P', name='P', unit_price=1)
        self.shelved = Pallet.objects.create(lot_number='S', product=p, quantity=1)
        Pallet.objects.create(lot_number='U', product=p, quantity=1)
        PalletLocation.objects.create(pallet=self.shelved, shelf=ShelfLocation.objects.create(code='QQ2', letter='QQ', story=2))
        StockAlert.objects.create(product=p, alert_type='expiry', message='x')
        StockAlert.objects.create(product=p, alert_type='low_stock', message='y', is_resolved=True)

    def test_pallet_location_filter(self):
        lots = lambda **q: [r['pallet'].lot_number for r in self.client.get(reverse('pallet_list'), q).context['pallet_data']]  # noqa: E731
        self.assertEqual(lots(location='unshelved'), ['U'])
        self.assertEqual(lots(location='shelved'), ['S'])
        self.assertEqual(sorted(lots()), ['S', 'U'])

    def test_alert_filters(self):
        types = lambda **q: [a.alert_type for a in self.client.get(reverse('alert_list'), q).context['alerts']]  # noqa: E731
        self.assertEqual(types(type='expiry'), ['expiry'])
        self.assertEqual(types(status='resolved'), ['low_stock'])
        self.assertEqual(len(types(type='bogus')), 2)
