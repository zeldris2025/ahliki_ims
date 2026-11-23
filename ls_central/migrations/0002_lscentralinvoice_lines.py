from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ls_central', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lscentralinvoice',
            name='lines',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
