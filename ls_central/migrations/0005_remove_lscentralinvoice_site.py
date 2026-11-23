from django.db import migrations


class Migration(migrations.Migration):
    # Separate from 0004 so the copy and the column change are separate transactions (PostgreSQL).

    dependencies = [
        ('ls_central', '0004_move_site_to_invoice'),
    ]

    operations = [
        migrations.RemoveField(model_name='lscentralinvoice', name='site'),
    ]
