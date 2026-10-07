from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import terminal49
from .models import Container, Product, ShipmentTracking, Supplier


def _plan_limited(*args, **kwargs):
    raise terminal49.Terminal49Error('You do not have permissions for using the API, except for creating '
                                     'tracking requests. All other permissions require a paid plan.',
                                     status=401, plan_limited=True)


@override_settings(TERMINAL49_API_KEY='test-key')
class ShipmentTrackingTests(TestCase):
    def setUp(self):
        self.broker = User.objects.create_user('broker', password='pw')
        self.broker.profile.role = 'custom_broker'
        self.broker.profile.save()
        self.client.login(username='broker', password='pw')
        self.supplier = Supplier.objects.create(name='Fonterra')

    def _track(self, **extra):
        data = {'request_number': ' mats 1234567 ', 'request_type': 'bill_of_lading', 'scac': '',
                'supplier': self.supplier.pk, 'origin_port': 'Auckland', 'vessel_name': 'Southern Moana',
                'eta_at': (timezone.localdate() + timedelta(days=3)).isoformat(),
                'container_numbers': 'msku1234565, MATU7654328', 'show_in_my_containers': 'on'}
        data.update(extra)
        return self.client.post(reverse('track_list'), data)

    def test_track_registers_with_terminal49_on_free_plan(self):
        created = {'data': {'id': 'tr-1', 'attributes': {'status': 'pending', 'scac': 'MATS'}}}
        with mock.patch.object(terminal49, '_request', return_value=created) as req:
            self._track()
        t = ShipmentTracking.objects.get()
        self.assertEqual(t.request_number, 'MATS1234567')
        self.assertEqual(t.container_number_list, ['MSKU1234565', 'MATU7654328'])
        self.assertEqual((t.t49_request_id, t.t49_status, t.scac), ('tr-1', 'pending', 'MATS'))
        payload = req.call_args.args[2]['data']['attributes']
        self.assertTrue(payload['auto_detect_vocc_scac'])
        self.assertNotIn('scac', payload)

        # Refreshing hits the paid-only read endpoint — the record keeps its estimate.
        with mock.patch.object(terminal49, '_request', side_effect=_plan_limited):
            self.client.post(reverse('track_refresh', args=[t.pk]))
        t.refresh_from_db()
        self.assertEqual(t.last_sync_message, terminal49.PLAN_LIMITED_MESSAGE)

    def test_demo_number_is_never_sent_to_terminal49(self):
        with mock.patch.object(terminal49, '_request') as req:
            resp = self._track(request_number='DEMO-BL-0099')
            self.client.post(reverse('track_refresh', args=[ShipmentTracking.objects.get().pk]))
        self.assertEqual(resp.status_code, 302)
        req.assert_not_called()
        self.assertIn('Demo shipment', ShipmentTracking.objects.get().last_sync_message)

    def test_random_numbers_rejected_before_reaching_terminal49(self):
        with mock.patch.object(terminal49, '_request') as req:
            bad_box = self._track(container_numbers='MSKU1234567')        # wrong check digit
            bad_bl = self._track(request_number='hello')                     # not a B/L
            bad_type = self._track(request_type='container', request_number='ABC123456')
        req.assert_not_called()
        self.assertContains(bad_box, 'fails the container check digit')
        self.assertContains(bad_box, 'would be 5')
        self.assertContains(bad_bl, 'does not look like a bill of lading number')
        self.assertContains(bad_type, 'is not a container number')
        self.assertFalse(ShipmentTracking.objects.exists())

    def test_container_number_sent_as_container_even_if_bl_picked(self):
        created = {'data': {'id': 'tr-2', 'attributes': {'status': 'pending'}}}
        with mock.patch.object(terminal49, '_request', return_value=created) as req:
            self._track(request_number='PDLU3208247', request_type='bill_of_lading', container_numbers='')
        self.assertEqual(req.call_args.args[2]['data']['attributes']['request_type'], 'container')
        t = ShipmentTracking.objects.get()
        self.assertEqual((t.request_type, t.container_numbers), ('container', 'PDLU3208247'))

    def test_stuck_record_is_resent_as_container_on_refresh(self):
        t = ShipmentTracking.objects.create(request_number='PDLU3208247', request_type='bill_of_lading')
        created = {'data': {'id': 'tr-3', 'attributes': {'status': 'pending'}}}
        with mock.patch.object(terminal49, '_request', return_value=created) as req:
            self.client.post(reverse('track_refresh', args=[t.pk]))
        self.assertEqual(req.call_args.args[2]['data']['attributes']['request_type'], 'container')
        t.refresh_from_db()
        self.assertEqual((t.request_type, t.t49_request_id), ('container', 'tr-3'))

    def test_number_terminal49_rejects_is_not_saved(self):
        rejected = terminal49.Terminal49Error('Request number is not valid for this carrier', status=422)
        with mock.patch.object(terminal49, '_request', side_effect=rejected):
            resp = self._track(request_number='MATS9999999999')
        self.assertContains(resp, 'Terminal49 could not find this number')
        self.assertFalse(ShipmentTracking.objects.exists())

    def test_new_container_needs_valid_number(self):
        product = Product.objects.create(sku='P2', name='Rice', unit_price=5, cost_price=3)
        post = {'container_number': 'RAND0M12345', 'supplier': self.supplier.pk,
                'items-TOTAL_FORMS': 1, 'items-INITIAL_FORMS': 0, 'items-MIN_NUM_FORMS': 0,
                'items-MAX_NUM_FORMS': 1000, 'items-0-product': product.pk, 'items-0-quantity': 1}
        resp = self.client.post(reverse('container_create'), post)
        self.assertContains(resp, 'is not a container number')
        self.assertFalse(Container.objects.exists())

    def test_duplicate_number_rejected(self):
        with mock.patch.object(terminal49, '_request', return_value={'data': {'id': 'x', 'attributes': {}}}):
            self._track()
            resp = self._track(request_number='MATS1234567')
        self.assertContains(resp, 'already being tracked')
        self.assertEqual(ShipmentTracking.objects.count(), 1)

    def test_network_failure_still_saves(self):
        with mock.patch.object(terminal49, '_request',
                               side_effect=terminal49.Terminal49Error('Could not reach Terminal49')):
            self._track()
        t = ShipmentTracking.objects.get()
        self.assertEqual(t.t49_status, 'not_sent')
        self.assertIn('Could not register', t.last_sync_message)

    def test_atlas_estimates_position_between_port_and_apia(self):
        now = timezone.now()
        t = ShipmentTracking.objects.create(request_number='BL1', origin_port='Shanghai',
                                            departed_at=now - timedelta(days=10), eta_at=now + timedelta(days=10))
        data = self.client.get(reverse('atlas_data')).json()
        ship = data['ships'][0]
        self.assertEqual(ship['id'], t.pk)
        self.assertEqual(ship['source'], 'estimated')
        self.assertAlmostEqual(ship['progress'], 0.5, places=2)
        # Route crosses the antimeridian without jumping and ends at Apia.
        lngs = [p[1] for p in ship['route']]
        self.assertTrue(all(abs(b - a) < 10 for a, b in zip(lngs, lngs[1:])))
        self.assertAlmostEqual(ship['route'][-1][1], terminal49.APIA['lng'] + 360, places=2)

    def test_unknown_port_is_listed_as_unplaced(self):
        ShipmentTracking.objects.create(request_number='BL2', origin_port='Atlantis')
        data = self.client.get(reverse('atlas_data')).json()
        self.assertEqual(data['ships'], [])
        self.assertEqual(data['unplaced'][0]['number'], 'BL2')

    def test_broker_pages_render(self):
        t = ShipmentTracking.objects.create(request_number='BL3', origin_port='NZAKL', supplier=self.supplier,
                                            container_numbers='ABCU1234560')
        for url in [reverse('container_list'), reverse('track_list'), reverse('track_edit', args=[t.pk]),
                    reverse('atlas'), f"{reverse('container_create')}?tracking={t.pk}"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        resp = self.client.get(reverse('container_list'))
        self.assertContains(resp, 'BL3')
        self.assertContains(self.client.get(f"{reverse('container_create')}?tracking={t.pk}"), 'value="ABCU1234560"')

    def test_lodging_from_tracking_marks_it_arrived(self):
        t = ShipmentTracking.objects.create(request_number='BL4', supplier=self.supplier,
                                            container_numbers='ABCU1234560')
        product = Product.objects.create(sku='P1', name='Milk', unit_price=5, cost_price=3)
        resp = self.client.post(reverse('container_create'), {
            'tracking': t.pk, 'container_number': 'abcu1234560', 'supplier': self.supplier.pk,
            'items-TOTAL_FORMS': 1, 'items-INITIAL_FORMS': 0, 'items-MIN_NUM_FORMS': 0, 'items-MAX_NUM_FORMS': 1000,
            'items-0-product': product.pk, 'items-0-quantity': 10,
        })
        self.assertEqual(resp.status_code, 302)
        c = Container.objects.get()
        self.assertEqual(c.tracking, t)
        t.refresh_from_db()
        self.assertIsNotNone(t.arrived_at)
        self.assertEqual(self.client.get(reverse('atlas_data')).json()['ships'], [])

    def test_add_supplier_tab_preselects_supplier(self):
        resp = self.client.post(reverse('container_create'), {'add_supplier': '1', 'sup-name': 'Goodman Fielder'})
        new = Supplier.objects.get(name='Goodman Fielder')
        self.assertRedirects(resp, f"{reverse('container_create')}?supplier={new.pk}")
        page = self.client.get(resp.url)
        self.assertContains(page, f'<option value="{new.pk}" selected>')

    def test_broker_cannot_reach_warehouse_only_pages(self):
        resp = self.client.get(reverse('warehouse_container_list'))
        self.assertRedirects(resp, reverse('container_list'))


@override_settings(TERMINAL49_API_KEY='test-key', TRACKING_AUTO_REFRESH_HOURS=4)
class AutoRefreshTests(TestCase):
    def _make(self, number, synced_hours_ago, **extra):
        extra.setdefault('t49_status', 'pending')
        t = ShipmentTracking.objects.create(request_number=number, t49_request_id=f'tr-{number}', **extra)
        if synced_hours_ago is not None:
            ShipmentTracking.objects.filter(pk=t.pk).update(
                last_synced_at=timezone.now() - timedelta(hours=synced_hours_ago))
        return t

    def test_only_stale_shipments_on_the_water_are_refreshed(self):
        stale = self._make('STALE', 5)
        never = self._make('NEVER', None)
        self._make('FRESH', 1)
        self._make('LANDED', 9, arrived_at=timezone.now())
        self._make('FAILED', 9, t49_status='failed')
        synced_numbers = []

        def fake_sync(t):
            synced_numbers.append(t.request_number)
            return True, 'ok'

        with mock.patch.object(terminal49, 'sync_tracking', side_effect=fake_sync):
            self.assertEqual(terminal49.refresh_stale(4), (2, 0))
        self.assertCountEqual(synced_numbers, ['STALE', 'NEVER'])
        # Claimed records are stamped, so a second pass (or another process) skips them.
        with mock.patch.object(terminal49, 'sync_tracking', side_effect=fake_sync):
            self.assertEqual(terminal49.refresh_stale(4), (0, 0))
        stale.refresh_from_db(); never.refresh_from_db()
        self.assertIsNotNone(never.last_synced_at)

    def test_refresher_does_not_start_outside_the_server(self):
        from . import auto_refresh
        with mock.patch.object(auto_refresh.sys, 'argv', ['manage.py', 'migrate']):
            self.assertFalse(auto_refresh.should_start())
        with mock.patch.object(auto_refresh.sys, 'argv', ['manage.py', 'runserver']), \
                mock.patch.dict(auto_refresh.os.environ, {'RUN_MAIN': 'true'}):
            self.assertTrue(auto_refresh.should_start())
        with override_settings(TRACKING_AUTO_REFRESH_HOURS=0), \
                mock.patch.object(auto_refresh.sys, 'argv', ['waitress-serve']):
            self.assertFalse(auto_refresh.should_start())
