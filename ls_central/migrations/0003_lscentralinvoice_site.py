from django.db import migrations, models


def fill_pos_sites(apps, schema_editor):
    """POS invoice numbers start with their site: HDQ-HDQ02-14375."""
    Record = apps.get_model('ls_central', 'LsCentralInvoice')
    for site in ('HDQ', 'SAV', 'TAU', 'VAI'):
        Record.objects.filter(ls_id__startswith=f'POS:{site}-').update(site=site)


class Migration(migrations.Migration):

    dependencies = [
        ('ls_central', '0002_lscentralinvoice_lines'),
    ]

    operations = [
        migrations.AddField(
            model_name='lscentralinvoice',
            name='site',
            field=models.CharField(blank=True, db_default='', default='', max_length=20),
        ),
        migrations.RunPython(fill_pos_sites, migrations.RunPython.noop),
    ]
