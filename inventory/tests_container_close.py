from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CmsContainer, Container, ContainerItem, Pallet, Product, ShippingLine, Yard


class ContainerCloseTests(TestCase):
    """Closing a container before everything is palletized, and re-opening it later."""

    def setUp(self):
        self.user = User.objects.create_user('wh', password='pw')
        self.user.profile.role = 'warehouse'
        self.user.profile.save()
        self.client.login(username='wh', password='pw')
        self.rice = Product.objects.create(sku='RICE', name='Rice', unit_price=10)

    def _opened(self, number, qty, palletized=0, cms=None):
        c = Container.objects.create(container_number=number, status=Container.STATUS_OPENED,
                                     opened_at=timezone.now(), cms_container=cms)
        item = ContainerItem.objects.create(container=c, product=self.rice, quantity=qty)
        if palletized:
            Pallet.objects.create(lot_number=f'LOT-{number}', product=self.rice, container_item=item,
                                  quantity=palletized)
        c.refresh_palletized_status()
        return c

    def _cms(self, code):
        return CmsContainer.objects.create(code=code, yard=Yard.objects.get(code='HQ-ALW-VAI'), status='full',
                                           owner=ShippingLine.objects.get(name='SWIRE'))

    def test_close_with_products_left_keeps_cms_box_full(self):
        cms = self._cms('SWLU1111111')
        c = self._opened('C-PART', qty=10, palletized=4, cms=cms)
        self.client.post(reverse('container_close', args=[c.pk]))
        c.refresh_from_db()
        cms.refresh_from_db()
        self.assertEqual(c.status, Container.STATUS_CLOSED)
        self.assertEqual(c.remaining_quantity, 6)
        self.assertEqual(cms.status, 'full')

    def test_close_when_empty_marks_cms_box_empty(self):
        cms = self._cms('SWLU2222222')
        c = self._opened('C-FULL', qty=10, palletized=10, cms=cms)
        self.client.post(reverse('container_close', args=[c.pk]))
        cms.refresh_from_db()
        self.assertEqual(cms.status, CmsContainer.STATUS_EMPTY)

    def test_reopen_then_finish(self):
        c = self._opened('C-AGAIN', qty=10, palletized=4)
        self.client.post(reverse('container_close', args=[c.pk]))
        self.client.post(reverse('container_reopen', args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(c.status, Container.STATUS_OPENED)
        self.assertIsNone(c.closed_at)
        response = self.client.post(reverse('container_palletize', args=[c.pk, c.items.get().pk]), {'quantity': 6})
        self.assertEqual(response.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.status, Container.STATUS_PALLETIZED)

    def test_empty_closed_container_cannot_be_reopened(self):
        c = self._opened('C-DONE', qty=5, palletized=5)
        self.client.post(reverse('container_close', args=[c.pk]))
        self.client.post(reverse('container_reopen', args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(c.status, Container.STATUS_CLOSED)

    def test_closed_tab_lists_containers_with_products_first(self):
        for number, qty, done in [('C-EMPTY', 5, 5), ('C-FEW', 10, 8), ('C-MANY', 10, 1)]:
            c = self._opened(number, qty, done)
            self.client.post(reverse('container_close', args=[c.pk]))
        closed = list(self.client.get(reverse('warehouse_container_list')).context['closed'])
        self.assertEqual([c.container_number for c in closed], ['C-MANY', 'C-FEW', 'C-EMPTY'])
        self.assertEqual([c.units_left for c in closed], [9, 2, 0])
