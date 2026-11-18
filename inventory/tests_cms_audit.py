from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CmsAuditLog, CmsContainer, Container, ShippingLine, Yard


class CmsAuditLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('mele', password='pw', first_name='Mele', last_name='Broker')
        self.user.profile.role = 'custom_broker'
        self.user.profile.save()
        self.client.login(username='mele', password='pw')
        self.hq = Yard.objects.get(code='HQ-ALW-VAI')
        self.palisi = Yard.objects.get(code='PALISI')
        self.swire = ShippingLine.objects.get(name='SWIRE')
        self.today = timezone.localdate()

    def _container(self, code='SWLU1234567', **extra):
        values = dict(code=code, yard=self.hq, status='full', owner=self.swire, arrival_date=self.today)
        values.update(extra)
        return CmsContainer.objects.create(**values)

    def _form(self, **overrides):
        data = {'code': 'SWLU1234567', 'description': 'Rice', 'yard': self.hq.pk, 'status': 'full',
                'owner': self.swire.pk, 'vessel_voyage': '', 'arrival_date': self.today.isoformat(),
                'driver': '', 'note': ''}
        data.update(overrides)
        return data

    def test_add_and_edit_record_who_and_what_changed(self):
        self.client.post(reverse('cms_container_add'), self._form(), HTTP_X_FORWARDED_FOR='203.0.113.9:51000')
        c = CmsContainer.objects.get()
        added = CmsAuditLog.objects.get(action='container_added')
        self.assertEqual((added.username, added.full_name, added.object_label, added.ip_address),
                         ('mele', 'Mele Broker', 'SWLU1234567', '203.0.113.9'))

        self.client.post(reverse('cms_container_edit', args=[c.pk]), self._form(status='storage', description='Flour'))
        edited = CmsAuditLog.objects.get(action='container_edited')
        self.assertEqual(edited.changes, {'Description': ['Rice', 'Flour'], 'Status': ['Full', 'Storage']})

    def test_transfer_return_undo_and_delete_are_logged(self):
        c = self._container()
        self.client.post(reverse('cms_container_transfer', args=[c.pk]),
                         {'to_yard': self.palisi.pk, 'transferred_date': self.today.isoformat(),
                          'driver': 'Tavita', 'staff_name': 'Mele', 'note': ''})
        moved = CmsAuditLog.objects.get(action='transferred')
        self.assertEqual(moved.changes['Yard'], ['HQ-ALW-VAI', 'PALISI'])
        self.client.post(reverse('cms_container_return', args=[c.pk]),
                         {'returned_date': self.today.isoformat(), 'staff_name': 'Mele', 'driver': 'Tavita'})
        self.assertTrue(CmsAuditLog.objects.filter(action='returned', object_label=c.code).exists())
        self.client.post(reverse('cms_return_undo', args=[c.returns.get().pk]))
        self.assertTrue(CmsAuditLog.objects.filter(action='return_undone').exists())
        self.client.post(reverse('cms_container_delete', args=[c.pk]))
        deleted = CmsAuditLog.objects.get(action='container_deleted')
        self.assertEqual(deleted.changes['Yard'], ['PALISI', ''])   # details survive the delete

    def test_bulk_status_logs_each_container(self):
        a, b = self._container('AAAU0000001'), self._container('AAAU0000002', status='empty')
        self.client.post(reverse('cms_container_bulk'), {'ids': [a.pk, b.pk], 'action': 'status', 'status': 'empty'})
        entries = CmsAuditLog.objects.filter(action='status_changed')
        self.assertEqual([e.object_label for e in entries], ['AAAU0000001'])   # b was already empty
        self.assertEqual(entries[0].source, 'Bulk action')

    def test_csv_import_logs_rows_and_a_summary(self):
        csv = ('Container Code,Description,Yard,Status,Owned,Vessel Voyage,A/Date,Driver,Note,Returned\n'
               'SWLU7777777,Rice,palisi,FULL,swire,,03/10/2026,,,No\n')
        self.client.post(reverse('cms_container_import'),
                         {'file': SimpleUploadedFile('boxes.csv', csv.encode(), content_type='text/csv')})
        self.client.post(reverse('cms_container_import'), {'confirm': '1'})
        self.assertEqual(CmsAuditLog.objects.get(action='container_added').source, 'CSV import boxes.csv')
        self.assertIn('boxes.csv: 1 added', CmsAuditLog.objects.get(action='imported').summary)

    def test_export_is_logged(self):
        self._container()
        self.client.get(reverse('cms_containers') + '?export=csv')
        e = CmsAuditLog.objects.get(action='exported')
        self.assertEqual((e.object_label, e.summary), ('Containers list', 'Exported 1 container(s) to CSV'))

    def test_warehouse_closing_an_empty_box_is_logged(self):
        cms = self._container()
        wh = User.objects.create_user('wh', password='pw')
        wh.profile.role = 'warehouse'
        wh.profile.save()
        box = Container.objects.create(container_number='WH-1', status=Container.STATUS_PALLETIZED, cms_container=cms)
        self.client.login(username='wh', password='pw')
        self.client.post(reverse('container_close', args=[box.pk]))
        e = CmsAuditLog.objects.get(action='status_changed')
        self.assertEqual((e.username, e.changes['Status'], e.source), ('wh', ['Full', 'Empty'], 'Warehouse: WH-1'))

    def test_entries_cannot_be_changed_or_deleted(self):
        c = self._container()
        self.client.post(reverse('cms_container_delete', args=[c.pk]))
        entry = CmsAuditLog.objects.get()
        entry.summary = 'tampered'
        with self.assertRaises(PermissionError):
            entry.save()
        with self.assertRaises(PermissionError):
            entry.delete()
        with self.assertRaises(PermissionError):
            CmsAuditLog.objects.all().delete()
        with self.assertRaises(PermissionError):
            CmsAuditLog.objects.update(summary='tampered')
        # Even raw SQL is refused by the database triggers.
        for sql in ("UPDATE inventory_cmsauditlog SET summary = 'tampered'", 'DELETE FROM inventory_cmsauditlog'):
            with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)
        self.assertEqual(CmsAuditLog.objects.get().summary, 'SWLU1234567 deleted from HQ-ALW-VAI')

    def test_page_is_view_only(self):
        self._container()
        self.client.get(reverse('cms_containers') + '?export=csv')
        page = self.client.get(reverse('cms_audit_log'))
        self.assertContains(page, 'Read-only record')
        self.assertContains(page, 'Exported 1 container(s) to CSV')
        self.assertEqual(self.client.post(reverse('cms_audit_log')).status_code, 405)
        self.client.force_login(User.objects.create_superuser('boss', password='pw'))
        entry = CmsAuditLog.objects.get()
        self.assertEqual(self.client.get(f'/admin/inventory/cmsauditlog/{entry.pk}/delete/').status_code, 403)
