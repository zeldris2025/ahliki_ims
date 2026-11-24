from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ls_central', '0005_remove_lscentralinvoice_site'),
    ]

    operations = [
        migrations.CreateModel(
            name='LsCentralPosDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(unique=True)),
                ('posted', models.PositiveIntegerField(default=0, help_text='POS invoices LS Central had for the day')),
                ('imported', models.PositiveIntegerField(default=0, help_text='Of those, how many are in the IMS')),
                ('complete', models.BooleanField(default=False, help_text="All of the day's posted invoices are imported")),
                ('checked_at', models.DateTimeField()),
            ],
            options={
                'verbose_name': 'LS Central POS day',
                'ordering': ['-day'],
            },
        ),
    ]
