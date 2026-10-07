from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CmsContainer, ContainerReturn, ShippingLine, Yard


class CmsTests(TestCase):
    def setUp(self):
        self.broker = User.objects.create_user('broker', password='pw', first_name='Mele', last_name='Broker')
        self.broker.profile.role = 'custom_broker'
        self.broker.profile.save()
        self.client.login(username='broker', password='pw')
        self.hq = Yard.objects.get(code='HQ-ALW-VAI')
        self.palisi = Yard.objects.get(code='PALISI')
        self.swire = ShippingLine.objects.get(name='SWIRE')
        self.swire.return_days = 10
        self.swire.save()
        self.today = timezone.localdate()

    def _container(self, code='SWLU1234567', days_ago=3, **extra):
        values = dict(code=code, yard=self.hq, status='full', owner=self.swire,
                      arrival_date=self.today - timedelta(days=days_ago))
        values.update(extra)
        return CmsContainer.objects.create(**values)

    def test_seeded_yards_and_owners(self):
        self.assertEqual(Yard.objects.count(), 13)
        self.assertEqual(set(ShippingLine.objects.values_list('name', flat=True)),
                         {'ALW', 'SWIRE', 'PFL', 'BBE/MSA', 'TSL'})

    def test_broker_lands_on_cms_and_old_pages_are_closed(self):
        self.assertRedirects(self.client.get('/'), reverse('cms_dashboard'))
        self.assertRedirects(self.client.get(reverse('container_list')), reverse('cms_dashboard'),
                             fetch_redirect_response=False)

    def test_every_page_renders(self):
        c = self._container(driver='Sione')
        for name, args in [('cms_dashboard', []), ('cms_containers', []), ('cms_container_add', []),
                           ('cms_container_edit', [c.pk]), ('cms_shipping', []), ('cms_returns', []),
                           ('cms_atlas', []), ('cms_container_import', [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        self.assertContains(self.client.get(reverse('cms_containers') + '?q=sione'), 'SWLU1234567')

    def test_add_container_and_reject_duplicate_in_yard(self):
        data = {'code': ' swlu 1234567 ', 'yard': self.hq.pk, 'status': 'full', 'owner': self.swire.pk,
                'arrival_date': self.today.isoformat(), 'driver': 'Sione'}
        self.client.post(reverse('cms_container_add'), data)
        c = CmsContainer.objects.get()
        self.assertEqual((c.code, c.driver, c.created_by), ('SWLU1234567', 'Sione', self.broker))
        resp = self.client.post(reverse('cms_container_add'), data)
        self.assertContains(resp, 'already in a yard')

    def test_deadlines(self):
        overdue = self._container('AAAU0000001', days_ago=12)
        soon = self._container('AAAU0000002', days_ago=5)
        no_deadline = self._container('AAAU0000003', owner=ShippingLine.objects.get(name='ALW'))
        self.assertEqual((overdue.days_left, overdue.days_overdue), (-2, 2))
        self.assertEqual(soon.days_left, 5)
        self.assertIsNone(no_deadline.days_left)
        resp = self.client.get(reverse('cms_containers') + '?due=overdue')
        self.assertEqual([c.code for c in resp.context['page']], ['AAAU0000001'])
        dash = self.client.get(reverse('cms_dashboard'))
        self.assertEqual([c.code for c in dash.context['due_soon']], ['AAAU0000001', 'AAAU0000002'])

    def test_return_with_driver_then_undo(self):
        c = self._container()
        self.client.post(reverse('cms_container_return', args=[c.pk]),
                         {'returned_date': self.today.isoformat(), 'staff_name': 'Mele', 'driver': 'Tavita'})
        c.refresh_from_db()
        r = ContainerReturn.objects.get()
        self.assertTrue(c.returned)
        self.assertEqual((r.location, r.staff_name, r.driver, r.yard), ('Wharf', 'Mele', 'Tavita', self.hq))
        # Same box can come back on a later voyage.
        self._container()
        self.client.post(reverse('cms_return_undo', args=[r.pk]))
        self.assertTrue(ContainerReturn.objects.exists())   # blocked: a later visit is in a yard
        CmsContainer.objects.filter(returned=False).delete()
        self.client.post(reverse('cms_return_undo', args=[r.pk]))
        c.refresh_from_db()
        self.assertFalse(c.returned)

    def test_bulk_move_and_return(self):
        a, b = self._container('AAAU0000001'), self._container('AAAU0000002')
        url = reverse('cms_container_bulk')
        self.client.post(url, {'ids': [a.pk, b.pk], 'action': 'move', 'yard': self.palisi.pk})
        self.assertEqual(CmsContainer.objects.filter(yard=self.palisi).count(), 2)
        self.client.post(url, {'ids': [a.pk, b.pk], 'action': 'return', 'returned_date': self.today.isoformat(),
                               'staff_name': 'Mele', 'driver': 'Tavita'})
        self.assertEqual(ContainerReturn.objects.filter(driver='Tavita', yard=self.palisi).count(), 2)

    def test_csv_import_preview_then_confirm(self):
        self._container('SWLU1234567', note='old')
        csv = ('Container Code,Description,Yard,Status,Owned,Vessel Voyage,A/Date,Driver,Note,Returned\n'
               'swlu1234567,Rice,palisi,STORAGE,swire,Lily 1,03/10/2026,Sione,new,No\n'
               'PFLU7654321,,MATAUTU,EMPTY,MSA,,2026-09-28,,,yes\n'
               'BADU0000001,,NOWHERE,FULL,SWIRE,,31/02/2026,,,maybe\n')
        upload = SimpleUploadedFile('c.csv', csv.encode('utf-8-sig'), content_type='text/csv')
        resp = self.client.post(reverse('cms_container_import'), {'file': upload})
        self.assertEqual(len(resp.context['rows']), 2)
        self.assertEqual(resp.context['update_count'], 1)
        (line, msg), = resp.context['errors']
        self.assertEqual(line, 4)
        for bit in ('NOWHERE', 'not a date', 'Yes or No'):
            self.assertIn(bit, msg)
        self.assertEqual(CmsContainer.objects.count(), 1)   # nothing written yet

        self.client.post(reverse('cms_container_import'), {'confirm': '1'})
        updated = CmsContainer.objects.get(code='SWLU1234567')
        self.assertEqual((updated.yard, updated.status, updated.note, updated.driver),
                         (self.palisi, 'storage', 'new', 'Sione'))
        returned = CmsContainer.objects.get(code='PFLU7654321')
        self.assertTrue(returned.returned)
        self.assertEqual(returned.owner.name, 'BBE/MSA')
        self.assertEqual(ContainerReturn.objects.get().container, returned)

    def test_shipping_line_crud(self):
        self.client.post(reverse('cms_shipping'), {'name': 'matson', 'return_days': 21})
        line = ShippingLine.objects.get(name='MATSON')
        self.assertEqual(line.return_days, 21)
        self._container(owner=line)
        self.client.post(reverse('cms_shipping_delete', args=[line.pk]))
        self.assertTrue(ShippingLine.objects.filter(pk=line.pk).exists())   # still owns a container

    def test_atlas_pin_move_stays_on_upolu(self):
        url = reverse('cms_yard_move', args=[self.hq.pk])
        self.assertEqual(self.client.post(url, {'lat': -13.84, 'lng': -171.80}).json()['ok'], True)
        self.assertEqual(self.client.post(url, {'lat': 51.5, 'lng': -0.1}).status_code, 400)
        self.hq.refresh_from_db()
        self.assertEqual((self.hq.latitude, self.hq.longitude), (-13.84, -171.8))

    def test_wharf_yard_adds_not_yet_released_note(self):
        wharf = Yard.objects.get(code='WHARF')
        self.client.post(reverse('cms_container_add'), {
            'code': 'AAAU0000001', 'yard': wharf.pk, 'status': 'full', 'owner': self.swire.pk, 'note': 'Seal 12'})
        self.assertEqual(CmsContainer.objects.get(code='AAAU0000001').note, 'NOT YET RELEASED\nSeal 12')

        moved = self._container('AAAU0000002')
        self.client.post(reverse('cms_container_bulk'), {'ids': [moved.pk], 'action': 'move', 'yard': wharf.pk})
        moved.refresh_from_db()
        self.assertEqual((moved.yard, moved.note), (wharf, 'NOT YET RELEASED'))
        moved.save()   # never added twice
        self.assertEqual(moved.note, 'NOT YET RELEASED')

        csv = 'Container Code,Yard,Status,Owned\nAAAU0000003,wharf,FULL,SWIRE\n'
        upload = SimpleUploadedFile('c.csv', csv.encode(), content_type='text/csv')
        self.client.post(reverse('cms_container_import'), {'file': upload})
        self.client.post(reverse('cms_container_import'), {'confirm': '1'})
        self.assertEqual(CmsContainer.objects.get(code='AAAU0000003').note, 'NOT YET RELEASED')

    def test_quick_filter_buttons(self):
        wharf = Yard.objects.get(code='WHARF')
        self._container('AAAU0000001', yard=wharf)
        self._container('AAAU0000002', status='empty')
        self._container('AAAU0000003', status='storage', days_ago=20)   # SWIRE: 10 return days -> overdue
        url = reverse('cms_containers')
        cases = [('', 'yards', 3), (f'?yard={wharf.pk}', 'wharf', 1), ('?status=empty', 'empty', 1),
                 ('?status=storage', 'storage', 1), ('?due=overdue', 'overdue', 1)]
        for query, tile, n in cases:
            resp = self.client.get(url + query)
            self.assertEqual((resp.context['tile'], resp.context['page'].paginator.count), (tile, n), query)
        stats = resp.context['stats']
        self.assertEqual((stats['active'], stats['wharf'], stats['empty'], stats['storage'], stats['overdue']),
                         (3, 1, 1, 1, 1))
        self.assertEqual(self.client.get(url + '?status=empty&yard=' + str(self.hq.pk)).context['tile'], '')

    def test_transfer_keeps_every_move(self):
        c = self._container()
        url = reverse('cms_container_transfer', args=[c.pk])
        kalua = Yard.objects.get(code='MATAUTU')
        for to, driver in ((self.palisi, 'Sione'), (kalua, 'Tavita'), (self.hq, '')):
            self.client.post(url, {'to_yard': to.pk, 'transferred_date': self.today.isoformat(),
                                   'driver': driver, 'staff_name': 'Mele', 'note': ''})
        c.refresh_from_db()
        self.assertEqual(c.yard, self.hq)
        trail = [(t.from_yard.code, t.to_yard.code, t.driver) for t in c.transfers.order_by('pk')]
        self.assertEqual(trail, [('HQ-ALW-VAI', 'PALISI', 'Sione'), ('PALISI', 'MATAUTU', 'Tavita'),
                                 ('MATAUTU', 'HQ-ALW-VAI', '')])
        # All three moves are visible on the container page, and the count shows in the list.
        page = self.client.get(reverse('cms_container_edit', args=[c.pk]))
        self.assertContains(page, 'Moved 3 times')
        self.assertContains(self.client.get(reverse('cms_containers')), '🔁 3 transfers')
        # Same yard is refused; bulk move is logged as a transfer too.
        self.client.post(url, {'to_yard': self.hq.pk, 'transferred_date': self.today.isoformat()})
        self.client.post(reverse('cms_container_bulk'), {'ids': [c.pk], 'action': 'move', 'yard': self.palisi.pk})
        self.assertEqual(c.transfers.count(), 4)
        self.assertEqual(c.transfers.first().note, 'Bulk move')

    def test_alw_containers_listed_last(self):
        alw = ShippingLine.objects.get(name='ALW')
        self._container('AAAU0000001', owner=alw, days_ago=30)     # oldest, but ALW
        self._container('ZZZU0000002', days_ago=1)
        self._container('MMMU0000003', days_ago=5)
        url = reverse('cms_containers')
        for sort in ('', '?sort=code', '?sort=-arrival', '?sort=owner'):
            codes = [c.code for c in self.client.get(url + sort).context['page']]
            self.assertEqual(codes[-1], 'AAAU0000001', sort)
