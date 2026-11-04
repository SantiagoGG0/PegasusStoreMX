import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0016_remove_orphaned_search_vector'),
        ('orders', '0006_order_group_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShippingExperimentEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('shown', 'Mostrado'), ('purchased_surcharge', 'Compró pagando el envío real'), ('chose_combo', 'Prefirió el combo sugerido')], max_length=24, verbose_name='Evento')),
                ('city', models.CharField(blank=True, max_length=200, verbose_name='Ciudad')),
                ('zone', models.CharField(blank=True, max_length=1, verbose_name='Zona')),
                ('shipping_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Cargo de envío mostrado/pagado')),
                ('session_key', models.CharField(blank=True, max_length=40, verbose_name='Sesión')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shipping_experiment_events', to='orders.order', verbose_name='Orden')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shipping_experiment_events', to='catalog.product', verbose_name='Producto')),
            ],
            options={
                'verbose_name': 'Evento de experimento de envío',
                'verbose_name_plural': 'Eventos de experimento de envío',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='shippingexperimentevent',
            index=models.Index(fields=['product', 'event_type'], name='catalog_shi_product_ff885e_idx'),
        ),
    ]
