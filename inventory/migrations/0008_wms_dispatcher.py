from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_wms_operator_role'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Admin'),
                    ('manager', 'Manager'),
                    ('finance', 'Finance'),
                    ('warehouse', 'Warehouse Lead'),
                    ('wms_operator', 'WMS Operator'),
                    ('wms_dispatcher', 'WMS Dispatcher'),
                    ('cashier', 'Sales / Cashier'),
                ],
                default='cashier',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='DispatchComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('invoice', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comments',
                    to='inventory.invoice',
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
