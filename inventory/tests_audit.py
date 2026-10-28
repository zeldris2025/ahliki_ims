from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AuditLog, Category, Product, Supplier, UserProfile


class AuditLogTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'pw')
        self.admin.profile.role = 'admin'
        self.admin.profile.save()
        self.broker = User.objects.create_user('broker', password='pw')
        self.broker.profile.role = 'custom_broker'
        self.broker.profile.save()
        AuditLog.objects.all().delete()

    def test_saves_outside_a_request_are_not_logged(self):
        Category.objects.create(name='Beverages')
        self.assertFalse(AuditLog.objects.exists())

    def test_login_logout_and_failed_login_are_logged(self):
        self.client.post(reverse('login'), {'username': 'broker', 'password': 'wrong'})
        self.client.post(reverse('login'), {'username': 'broker', 'password': 'pw'})
        self.client.post(reverse('logout'))
        actions = list(AuditLog.objects.order_by('id').values_list('action', 'username', 'department'))
        self.assertEqual(actions, [
            ('login_failed', 'broker', 'system'),
            ('login', 'broker', 'containers'),
            ('logout', 'broker', 'containers'),
        ])

    def test_create_update_delete_record_who_and_what_changed(self):
        self.client.force_login(self.admin)
        cat = Category.objects.create(name='Dry Goods')
        sup = Supplier.objects.create(name='Pacific Foods')
        self.client.post(reverse('admin:inventory_category_add'), {'name': 'Beverages', 'description': ''})
        product_add = reverse('admin:inventory_product_add')
        self.client.post(product_add, {'sku': 'BEV-1', 'name': 'Cola', 'category': cat.pk, 'supplier': sup.pk, 'unit_price': '8.50',
                                       'cost_price': '6', 'reorder_level': 10, 'unit': 'each', 'is_active': 'on'})
        product = Product.objects.get(sku='BEV-1')
        self.client.post(reverse('admin:inventory_product_change', args=[product.pk]),
                         {'sku': 'BEV-1', 'name': 'Cola 1.5L', 'category': cat.pk, 'supplier': sup.pk, 'unit_price': '9.00',
                          'cost_price': '6', 'reorder_level': 10, 'unit': 'each', 'is_active': 'on'})
        self.client.post(reverse('admin:inventory_product_delete', args=[product.pk]), {'post': 'yes'})

        created = AuditLog.objects.get(action='create', object_type='Product')
        self.assertEqual((created.username, created.department, created.area), ('boss', 'management', 'products'))
        self.assertEqual(created.changes['category'], ['', 'Dry Goods'])

        updated = AuditLog.objects.get(action='update', object_type='Product')
        self.assertEqual(updated.changes['name'], ['Cola', 'Cola 1.5L'])
        self.assertEqual(updated.changes['unit_price'], ['8.50', '9.00'])
        self.assertNotIn('sku', updated.changes)

        self.assertTrue(AuditLog.objects.filter(action='delete', object_type='Product', object_id=str(product.pk)).exists())

    def test_password_values_are_never_stored(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('admin:auth_user_password_change', args=[self.broker.pk]),
                         {'password1': 'N3w-secret-pw!', 'password2': 'N3w-secret-pw!', 'usable_password': 'true'})
        entry = AuditLog.objects.get(action='update', object_type='User')
        self.assertEqual(entry.changes['password'], ['••••••', '••••••'])
        self.assertNotIn('N3w-secret-pw!', str(entry.changes))

    def test_audit_log_is_read_only_in_admin(self):
        self.client.post(reverse('login'), {'username': 'broker', 'password': 'pw'})
        entry = AuditLog.objects.get(action='login')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('admin:inventory_auditlog_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:inventory_auditlog_change', args=[entry.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:inventory_auditlog_add')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:inventory_auditlog_delete', args=[entry.pk]),
                                          {'post': 'yes'}).status_code, 403)
        self.assertTrue(AuditLog.objects.filter(pk=entry.pk).exists())

    def test_staff_can_be_filtered_by_department(self):
        self.client.force_login(self.admin)
        url = reverse('admin:auth_user_changelist')
        users = list(self.client.get(url, {'department': 'containers'}).context['cl'].result_list)
        self.assertEqual(users, [self.broker])
        users = list(self.client.get(url, {'department': 'management'}).context['cl'].result_list)
        self.assertEqual(users, [self.admin])

    def test_superuser_counts_as_management_whatever_their_role(self):
        self.admin.profile.role = 'cashier'
        self.admin.profile.save()
        self.assertEqual(UserProfile.objects.get(user=self.admin).department, 'management')
        self.client.force_login(self.admin)
        url = reverse('admin:auth_user_changelist')
        self.assertEqual(list(self.client.get(url, {'department': 'sales'}).context['cl'].result_list), [])
        profiles = self.client.get(reverse('admin:inventory_userprofile_changelist'), {'department': 'management'})
        self.assertEqual([p.user for p in profiles.context['cl'].result_list], [self.admin])
        self.client.post(reverse('login'), {'username': 'boss', 'password': 'pw'})
        self.assertEqual(AuditLog.objects.get(action='login', path=reverse('login')).department, 'management')
        self.assertEqual(UserProfile.objects.get(user=self.broker).get_department_display(), 'Containers (CMS)')
