from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_wms'),
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
                    ('cashier', 'Sales / Cashier'),
                ],
                default='cashier',
                max_length=20,
            ),
        ),
    ]
