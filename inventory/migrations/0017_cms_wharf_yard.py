from django.db import migrations


def add_wharf(apps, schema_editor):
    Yard = apps.get_model('inventory', 'Yard')
    # Apia port, Matautu-tai.
    Yard.objects.get_or_create(code='WHARF', defaults={
        'description': 'Apia Wharf — not yet released', 'latitude': -13.8213, 'longitude': -171.7566,
        'sort_order': 12})


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0016_cms_driver'),
    ]

    operations = [
        migrations.RunPython(add_wharf, migrations.RunPython.noop),
    ]
