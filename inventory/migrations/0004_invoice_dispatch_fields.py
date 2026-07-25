import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_alter_userprofile_role'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='dispatch_status',
            field=models.CharField(
                choices=[('pending', 'Pending Dispatch'), ('dispatched', 'Dispatched')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='dispatched_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='dispatched_invoices',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='dispatched_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
