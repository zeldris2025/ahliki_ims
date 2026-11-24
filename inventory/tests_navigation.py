"""The sidebar menu only offers pages the backend lets each role open."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .navigation import ALL_ROLES, SECTIONS, view_roles


def _user(role, superuser=False):
    user = User.objects.create_user(f'u_{role}_{int(superuser)}', password='pw', is_superuser=superuser,
                                    is_staff=superuser)
    user.profile.role = role
    user.profile.sites = 'HDQ'
    user.profile.save()
    return user


def _hrefs(response):
    return [i['href'] for s in response.context['nav_menu'] for i in s['items']]


class MenuMatchesPermissionsTests(TestCase):
    def test_every_link_role_is_allowed_by_its_view(self):
        """A role listed on a menu link must be admitted by that view's @role_required."""
        problems = []
        for section in SECTIONS:
            for item in section.items:
                if item.staff_only:
                    continue
                allowed = view_roles(item.url_name)
                if allowed is None:      # login only
                    continue
                for role in item.roles:
                    if role not in allowed:
                        problems.append(f'{item.label} ({item.url_name}) is shown to {role}')
        self.assertEqual(problems, [])

    def test_every_visible_link_opens_for_each_role(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                user = _user(role)
                self.client.force_login(user)
                home = self.client.get(reverse('home'), follow=True)
                self.assertEqual(home.status_code, 200)
                for href in _hrefs(home):
                    response = self.client.get(href)
                    self.assertEqual(response.status_code, 200, f'{role} → {href} gave {response.status_code}')
                self.client.logout()

    def test_superuser_sees_admin_links(self):
        self.client.force_login(_user('cashier', superuser=True))
        hrefs = _hrefs(self.client.get(reverse('dashboard')))
        for name in ('user_list', 'ls_central:status', 'cms_dashboard', 'warehouse_dispatch_list', 'admin:index'):
            self.assertIn(reverse(name), hrefs)


class MenuContentsTests(TestCase):
    def menu_for(self, role, url_name):
        self.client.force_login(_user(role))
        return _hrefs(self.client.get(reverse(url_name)))

    def test_cashier_sees_sales_only(self):
        hrefs = self.menu_for('cashier', 'invoice_upload')
        self.assertIn(reverse('invoice_upload'), hrefs)
        self.assertIn(reverse('stock_lookup'), hrefs)
        for name in ('user_list', 'reports', 'warehouse_dispatch_list', 'cms_dashboard', 'pallet_list'):
            self.assertNotIn(reverse(name), hrefs)

    def test_custom_broker_sees_cms_only(self):
        hrefs = self.menu_for('custom_broker', 'cms_dashboard')
        self.assertTrue(hrefs)
        self.assertTrue(all(h.startswith('/cms/') for h in hrefs), hrefs)

    def test_dispatcher_gets_dispatch_and_history(self):
        hrefs = self.menu_for('wms_dispatcher', 'wms_dispatcher_dashboard')
        self.assertIn(reverse('warehouse_dispatch_list'), hrefs)
        self.assertIn(reverse('warehouse_dispatch_list') + '?tab=log', hrefs)
        self.assertNotIn(reverse('user_list'), hrefs)

    def test_active_link_and_breadcrumb(self):
        self.client.force_login(_user('admin'))
        response = self.client.get(reverse('warehouse_dispatch_list') + '?tab=log')
        self.assertEqual(response.context['nav_current'][:2], ('Sales & Dispatch', 'Dispatch History'))
        response = self.client.get(reverse('warehouse_dispatch_list'))
        self.assertEqual(response.context['nav_current'][:2], ('Sales & Dispatch', 'Warehouse Dispatch'))
        active = [i['label'] for s in response.context['nav_menu'] for i in s['items'] if i['active']]
        self.assertEqual(active, ['Warehouse Dispatch'])

    def test_non_staff_admin_role_gets_no_django_admin_links(self):
        hrefs = self.menu_for('admin', 'dashboard')
        self.assertNotIn(reverse('admin:index'), hrefs)
        self.assertIn(reverse('user_list'), hrefs)
