from django.db import migrations

# Approximate pin positions around Apia / Vaitele — drag a pin on the Ah Liki Atlas
# (Adjust pins) to correct it.
YARDS = [
    ('HQ-ALW-VAI', 'Ah Liki HQ, Vaitele', -13.8352, -171.8136),
    ('PALISI', 'Palisi', -13.8590, -171.7720),
    ('FJOE', 'FJOE', -13.8272, -171.8052),
    ('TAUFUSI', 'Taufusi', -13.8392, -171.7602),
    ('MALIFA', 'Malifa', -13.8352, -171.7690),
    ('KCL', 'KCL', -13.8302, -171.8176),
    ('FJOE-ALW-VAI', 'FJOE / Ah Liki, Vaitele', -13.8392, -171.8205),
    ('VAI-UTA-SIONE', 'Vaitele-uta (Sione)', -13.8484, -171.8118),
    ('TAULA', 'Taula, Vaitele', -13.8334, -171.8248),
    ('FARM', 'Farm', -13.8705, -171.8610),
    ('NSW-TARO-PACKING', 'NSW taro packing', -13.8445, -171.8365),
    ('MATAUTU', 'Matautu', -13.8238, -171.7538),
]

OWNERS = ['ALW', 'SWIRE', 'PFL', 'BBE/MSA', 'TSL']


def seed(apps, schema_editor):
    Yard = apps.get_model('inventory', 'Yard')
    ShippingLine = apps.get_model('inventory', 'ShippingLine')
    for i, (code, description, lat, lng) in enumerate(YARDS):
        Yard.objects.get_or_create(code=code, defaults={
            'description': description, 'latitude': lat, 'longitude': lng, 'sort_order': i})
    for name in OWNERS:
        ShippingLine.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0014_cms'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
