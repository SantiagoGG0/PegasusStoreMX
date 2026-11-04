from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_order_cancel_pending_dropi_order_cancel_reason_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="shipping_cost",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=12,
                verbose_name="Costo de envío",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="carrier",
            field=models.CharField(blank=True, max_length=120, verbose_name="Transportadora"),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_url",
            field=models.URLField(blank=True, max_length=500, verbose_name="Seguimiento"),
        ),
    ]
