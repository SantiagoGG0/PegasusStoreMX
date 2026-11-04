from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_order_group_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='needs_manual_supplier',
            field=models.BooleanField(
                default=False,
                help_text='El proveedor asignado no tenía stock al momento del pedido. El pedido se creó igual (sin enviarse a Dropi) para reasignarlo a mano a otro proveedor y confirmarlo desde aquí.',
                verbose_name='Requiere proveedor manual',
            ),
        ),
    ]
