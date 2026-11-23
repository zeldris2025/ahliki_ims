import re
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import SITES, AuditLog, DispatchComment, Invoice, InvoiceItem, Product, StockMovement, UserProfile
from .site_access import visible_invoices

INVOICE_ROLES = ('manager', 'finance', 'warehouse', 'wms_operator', 'wms_dispatcher', 'cashier', 'custom_broker')


def staff(name, role, sites=''):
    user = User.objects.create_user(name, password='pw')
    UserProfile.objects.update_or_create(user=user, defaults={'role': role, 'sites': sites})
    return User.objects.get(pk=user.pk)


@override_settings(LS_CENTRAL_TENANT_ID='')     # never call LS Central from a test
class SiteAccessTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(sku='RICE', name='Rice', unit_price=5)
        self.pending, self.done = {}, {}
        for site in SITES:
            self.pending[site] = Invoice.objects.create(
                invoice_number=f'PENDING-{site}', site=site, customer_name=f'Customer of {site}')
            InvoiceItem.objects.create(invoice=self.pending[site], product=self.product, quantity=2, unit_price=5)
            self.done[site] = Invoice.objects.create(
                invoice_number=f'DONE-{site}', site=site, customer_name=f'Past customer of {site}',
                dispatch_status='dispatched', dispatched_at=timezone.now())
            StockMovement.objects.create(product=self.product, movement_type='out', quantity=-1,
                                         reference=f'DONE-{site}')
        self.unsited = Invoice.objects.create(invoice_number='UNSITED', customer_name='Nobody')

    def login(self, role, sites=''):
        user = staff(f'{role}-{sites or "none"}', role, sites)
        self.client.force_login(user)
        return user

    def test_each_role_sees_only_its_site(self):
        for role in INVOICE_ROLES:
            for site in SITES:
                seen = set(visible_invoices(staff(f'{role}{site}', role, site)))
                self.assertEqual(seen, {self.pending[site], self.done[site]}, (role, site))

    def test_no_site_sees_nothing(self):
        for role in INVOICE_ROLES:
            self.assertFalse(visible_invoices(staff(f'{role}0', role)).exists(), role)

    def test_several_sites(self):
        seen = set(visible_invoices(staff('two', 'finance', 'SAV,VAI')).values_list('site', flat=True))
        self.assertEqual(seen, {'SAV', 'VAI'})

    def test_admins_and_superusers_see_everything(self):
        boss = User.objects.create_superuser('boss', password='pw')
        for user in (boss, staff('office', 'admin')):
            self.assertEqual(visible_invoices(user).count(), 9)

    def test_unknown_site_values_grant_nothing(self):
        self.assertFalse(visible_invoices(staff('odd', 'finance', 'CRP,,hdq')).exists())

    def test_direct_urls_of_another_site_are_not_found(self):
        urls = {'manager': ['invoice_detail', 'picking_ticket'],
                'finance': ['invoice_detail'],
                'cashier': ['invoice_detail'],
                'custom_broker': ['invoice_detail'],
                'wms_operator': ['invoice_detail', 'picking_ticket'],
                'warehouse': ['invoice_detail', 'picking_ticket', 'warehouse_dispatch_detail', 'dispatcher_edit_order'],
                'wms_dispatcher': ['invoice_detail', 'picking_ticket', 'warehouse_dispatch_detail',
                                   'dispatcher_edit_order']}
        for role, names in urls.items():
            self.login(role, 'HDQ')
            for name in names:
                for other in (self.pending['SAV'], self.unsited):
                    self.assertEqual(self.client.get(reverse(name, args=[other.pk])).status_code, 404, (role, name))
                self.assertEqual(self.client.get(reverse(name, args=[self.pending['HDQ'].pk])).status_code, 200,
                                 (role, name))

    def test_actions_on_another_site_change_nothing(self):
        self.login('wms_dispatcher', 'HDQ')
        other = self.pending['SAV']
        item = other.items.get()
        for name, data in (
                ('warehouse_dispatch_detail', {'add_comment': '1', 'comment_body': 'hello'}),
                ('warehouse_dispatch_submit', {'truck_plate': 'S1', 'checked_items': [item.pk]}),
                ('dispatcher_add_comment', {'body': 'hello'}),
                ('dispatcher_edit_order', {'edit_reason': 'x', f'action_{item.pk}': 'delete'})):
            self.assertEqual(self.client.post(reverse(name, args=[other.pk]), data).status_code, 404, name)
        other.refresh_from_db()
        self.assertEqual((other.dispatch_status, other.status, other.items.count()), ('pending', 'unpaid', 1))
        self.assertFalse(DispatchComment.objects.exists())
        self.assertEqual(StockMovement.objects.count(), 4)

    def test_item_of_another_site_cannot_be_edited_through_own_invoice(self):
        self.login('wms_dispatcher', 'HDQ')
        foreign = self.pending['SAV'].items.get()
        self.client.post(reverse('dispatcher_edit_order', args=[self.pending['HDQ'].pk]),
                         {'edit_reason': 'x', f'action_{foreign.pk}': 'delete'})
        self.assertTrue(InvoiceItem.objects.filter(pk=foreign.pk).exists())

    def test_every_listing_shows_only_own_site(self):
        pages = {'warehouse': ['dashboard', 'invoice_list', 'warehouse_dispatch_list', 'warehouse_dispatch_export',
                               'stock_movements', 'wms_dispatcher_dashboard'],
                 'manager': ['dashboard', 'invoice_list', 'manager_dashboard', 'wms_dispatcher_dashboard']}
        for role, names in pages.items():
            self.login(role, 'HDQ')
            urls = [reverse(name) for name in names] + [reverse('product_detail', args=[self.product.pk])]
            for url in urls:
                body = self.client.get(url).content.decode()
                leaked = re.findall(r'(?:PENDING|DONE)-(?:SAV|TAU|VAI)|ustomer of (?:SAV|TAU|VAI)|UNSITED', body)
                self.assertEqual(leaked, [], (role, url))

    def test_counts_are_for_own_site(self):
        self.login('warehouse', 'HDQ')
        self.assertEqual(self.client.get(reverse('dashboard')).context['pending_dispatch_count'], 1)
        self.assertEqual(self.client.get(reverse('wms_dispatcher_dashboard')).context['pending_count'], 1)
        options = self.client.get(reverse('warehouse_dispatch_list')).context['site_options']
        self.assertEqual([(o['code'], o['pending'], o['dispatched']) for o in options], [('HDQ', 1, 1)])

    def test_filter_cannot_widen_access(self):
        self.login('wms_dispatcher', 'HDQ')
        page = self.client.get(reverse('warehouse_dispatch_list') + '?site=SAV&site=OTHER')
        self.assertEqual([i.site for i in page.context['pending']], ['HDQ'])
        body = self.client.get(reverse('warehouse_dispatch_export') + '?site=SAV').content.decode()
        self.assertNotIn('DONE-SAV', body)

    def test_removing_a_site_applies_to_an_open_session(self):
        user = self.login('wms_dispatcher', 'HDQ,SAV')
        self.client.get(reverse('warehouse_dispatch_list') + '?site=SAV')
        UserProfile.objects.filter(user=user).update(sites='HDQ')
        page = self.client.get(reverse('warehouse_dispatch_list'))
        self.assertEqual([i.site for i in page.context['pending']], ['HDQ'])

    def test_pdfs_follow_the_site(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'invoices').mkdir()
            for name in ('sav.pdf', 'stray.pdf', 'page.html'):
                (Path(root) / 'invoices' / name).write_bytes(b'content')
            Invoice.objects.filter(pk=self.pending['SAV'].pk).update(invoice_file='invoices/sav.pdf')
            Invoice.objects.filter(pk=self.done['SAV'].pk).update(invoice_file='invoices/page.html')
            with self.settings(MEDIA_ROOT=root):
                self.login('finance', 'HDQ')
                for path in ('invoices/sav.pdf', 'invoices/SAV.PDF', 'invoices/../invoices/sav.pdf',
                             'invoices/stray.pdf', 'invoices/', ''):
                    self.assertEqual(self.client.get(f'/media/{path}').status_code, 404, path)
                self.client.force_login(staff('sav-fin', 'finance', 'SAV'))
                resp = self.client.get('/media/invoices/sav.pdf')
                self.assertEqual((resp.status_code, b''.join(resp.streaming_content)), (200, b'content'))
                resp.close()
                resp = self.client.get('/media/invoices/page.html')     # never run as a page
                self.assertTrue(resp['Content-Disposition'].startswith('attachment'))
                resp.close()
                self.assertEqual(self.client.get('/media/invoices/stray.pdf').status_code, 404)

    def upload(self, number, **extra):
        return self.client.post(reverse('invoice_upload'), {
            'invoice_number': number, 'payment_method': 'cash', 'total_amount': '10', 'tax_amount': '1', **extra})

    def test_upload_gets_the_uploaders_site(self):
        self.login('cashier', 'TAU')
        self.upload('UP-1', site='HDQ')     # a forged site is ignored
        self.assertEqual(Invoice.objects.get(invoice_number='UP-1').site, 'TAU')

    def test_upload_with_several_sites_must_pick_one_of_them(self):
        self.login('cashier', 'TAU,VAI')
        self.upload('UP-2')
        self.upload('UP-3', site='HDQ')
        self.assertFalse(Invoice.objects.filter(invoice_number__in=['UP-2', 'UP-3']).exists())
        self.upload('UP-4', site='VAI')
        self.assertEqual(Invoice.objects.get(invoice_number='UP-4').site, 'VAI')

    def test_upload_without_a_site_is_refused(self):
        self.login('cashier')
        self.assertEqual(self.upload('UP-5').status_code, 200)
        self.assertFalse(Invoice.objects.filter(invoice_number='UP-5').exists())

    def test_admin_assigns_sites_and_it_is_audited(self):
        self.login('admin')
        target = staff('target', 'wms_dispatcher')
        self.client.post(reverse('user_edit', args=[target.pk]),
                         {'role': 'wms_dispatcher', 'is_active': 'on', 'sites': ['VAI', 'HDQ', 'BOGUS']})
        self.assertEqual(UserProfile.objects.get(user=target).sites, 'HDQ,VAI')
        self.assertTrue(any('sites' in e.changes for e in AuditLog.objects.filter(object_type__iexact='user profile')))
        self.client.post(reverse('user_add'), {'username': 'new', 'password': 'pw', 'role': 'cashier', 'sites': ['SAV']})
        self.assertEqual(UserProfile.objects.get(user__username='new').sites, 'SAV')
        self.assertContains(self.client.get(reverse('user_list')), 'VAI')

    def test_users_cannot_give_themselves_a_site(self):
        user = self.login('warehouse', 'HDQ')
        self.client.post(reverse('profile'), {'first_name': 'A', 'sites': ['SAV'], 'role': 'admin'})
        self.client.post(reverse('user_edit', args=[user.pk]), {'role': 'admin', 'sites': ['SAV']})
        profile = UserProfile.objects.get(user=user)
        self.assertEqual((profile.role, profile.sites), ('warehouse', 'HDQ'))

    def test_nobody_can_mark_an_invoice_paid(self):
        invoice = self.pending['HDQ']
        users = [User.objects.create_superuser('super', password='pw'), staff('office-admin', 'admin')]
        users += [staff(f'pay-{role}', role, 'HDQ') for role in INVOICE_ROLES]
        for user in users:
            self.client.force_login(user)
            url = f'/invoices/{invoice.pk}/pay/'
            self.assertEqual(self.client.post(url, {'payment_method': 'cash'}).status_code, 404, user.username)
            self.assertEqual(self.client.get(url).status_code, 404, user.username)
            page = self.client.get(reverse('invoice_detail', args=[invoice.pk]))
            self.assertEqual(page.status_code, 200, user.username)
            for text in ('Mark as Paid', 'payModal', 'Confirm Paid'):
                self.assertNotContains(page, text)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'unpaid')

    def test_invoice_number_cannot_inject_script(self):
        nasty = "X');alert(1);//"
        Invoice.objects.filter(pk=self.pending['HDQ'].pk).update(invoice_number=nasty)
        self.login('wms_dispatcher', 'HDQ')
        for name in ('warehouse_dispatch_detail', 'dispatcher_edit_order'):
            body = self.client.get(reverse(name, args=[self.pending['HDQ'].pk])).content.decode()
            for handler in re.findall(r'confirm\([^"]*', body):
                self.assertNotIn('&#x27;);alert', handler, name)


class InvoiceListPagingTests(TestCase):
    def setUp(self):
        now = timezone.now()
        for n in range(65):
            Invoice.objects.create(invoice_number=f'H{n:03}', site='HDQ', created_at=now - timezone.timedelta(minutes=n))
        Invoice.objects.create(invoice_number='SAV-ONLY', site='SAV', created_at=now)
        self.client.force_login(staff('fin', 'finance', 'HDQ'))

    def numbers(self, query=''):
        return [i.invoice_number for i in self.client.get(reverse('invoice_list') + query).context['invoices']]

    def test_thirty_per_page_newest_first(self):
        self.assertEqual(self.numbers(), [f'H{n:03}' for n in range(30)])
        self.assertEqual(self.numbers('?page=3'), [f'H{n:03}' for n in range(60, 65)])
        page = self.client.get(reverse('invoice_list') + '?page=2')
        self.assertContains(page, '31–60 of 65')
        self.assertContains(page, 'href="?page=3"')

    def test_pages_cover_every_invoice_once_and_no_other_site(self):
        seen = sum((self.numbers(f'?page={n}') for n in (1, 2, 3)), [])
        self.assertEqual(sorted(seen), [f'H{n:03}' for n in range(65)])

    def test_bad_page_numbers_are_safe(self):
        self.assertEqual(self.numbers('?page=99')[-1], 'H064')
        self.assertEqual(self.numbers('?page=x')[0], 'H000')

    def test_no_pager_when_one_page(self):
        Invoice.objects.filter(invoice_number__gte='H010').delete()
        self.assertNotContains(self.client.get(reverse('invoice_list')), 'Page 1 /')
