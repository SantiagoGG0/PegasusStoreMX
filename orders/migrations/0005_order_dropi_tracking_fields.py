from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_shipping_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="shipping_guide",
            field=models.CharField(blank=True, max_length=100, verbose_name="Número de guía"),
        ),
        migrations.AddField(
            model_name="order",
            name="dropi_status",
            field=models.CharField(blank=True, max_length=100, verbose_name="Estado en Dropi"),
        ),
        migrations.AddField(
            model_name="order",
            name="last_dropi_sync",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Última sync Dropi"),
        ),
    ]
