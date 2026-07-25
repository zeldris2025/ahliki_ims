from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_invoice_dispatch_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='truck_plate',
            field=models.CharField(
                blank=True,
                help_text='Delivery truck plate number',
                max_length=50,
            ),
        ),
    ]
