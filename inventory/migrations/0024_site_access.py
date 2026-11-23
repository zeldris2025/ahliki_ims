from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0023_cms_audit_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='site',
            field=models.CharField(blank=True, db_default='', default='', max_length=20),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='sites',
            field=models.CharField(blank=True, db_default='', default='', max_length=100,
                                   help_text='Set on the Users page. The Admin role sees every site.'),
        ),
    ]
