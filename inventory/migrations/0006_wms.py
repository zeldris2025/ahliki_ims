import string
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_shelf_locations(apps, schema_editor):
    ShelfLocation = apps.get_model('inventory', 'ShelfLocation')
    for letter in string.ascii_uppercase:           # A – Z
        for story in range(1, 4):                   # 1, 2, 3
            ShelfLocation.objects.get_or_create(
                code=f"{letter}{story}",
                defaults={'letter': letter, 'story': story},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_invoice_truck_plate'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Update UserProfile role choices ─────────────────────────────────
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Admin'),
                    ('manager', 'Manager'),
                    ('finance', 'Finance'),
                    ('warehouse', 'Warehouse Lead'),
                    ('cashier', 'Sales / Cashier'),
                ],
                default='cashier',
                max_length=20,
            ),
        ),

        # ── ShelfLocation ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ShelfLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10, unique=True)),
                ('letter', models.CharField(max_length=1)),
                ('story', models.PositiveSmallIntegerField()),
            ],
            options={'ordering': ['letter', 'story']},
        ),

        # ── Pallet ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Pallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lot_number', models.CharField(max_length=100, unique=True)),
                ('quantity', models.PositiveIntegerField()),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pallets',
                    to='inventory.product',
                )),
                ('grn_item', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pallets',
                    to='inventory.grnitem',
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pallets_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),

        # ── PalletLocation ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='PalletLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_current', models.BooleanField(default=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
                ('pallet', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='location_history',
                    to='inventory.pallet',
                )),
                ('shelf', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pallet_assignments',
                    to='inventory.shelflocation',
                )),
                ('assigned_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='shelf_assignments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),

        # ── Populate A1–Z3 shelf locations ───────────────────────────────────
        migrations.RunPython(create_shelf_locations, migrations.RunPython.noop),
    ]
