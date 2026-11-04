from django.core.validators import MaxValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_herobanner_object_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="category_confidence",
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[MaxValueValidator(100)],
                verbose_name="Confianza categoría",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="category_locked",
            field=models.BooleanField(
                default=False,
                help_text="Si está activo, la sincronización de Dropi no cambia la categoría Pegasus.",
                verbose_name="Bloquear categoría",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="category_reason",
            field=models.CharField(blank=True, max_length=255, verbose_name="Razón de categorización"),
        ),
        migrations.AddField(
            model_name="product",
            name="dropi_category_id",
            field=models.CharField(blank=True, max_length=100, verbose_name="ID categoría Dropi"),
        ),
        migrations.AddField(
            model_name="product",
            name="dropi_category_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="Categoría Dropi original"),
        ),
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.ForeignKey(
                blank=True,
                help_text="Categoría curada visible en tienda. No depende directamente de Dropi.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="catalog.category",
                verbose_name="Categoría Pegasus",
            ),
        ),
    ]
