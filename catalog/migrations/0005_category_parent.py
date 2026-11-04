import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_category_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                help_text='Deja vacío para categorías principales. Selecciona una categoría padre para crear una subcategoría.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children',
                to='catalog.category',
                verbose_name='Categoría padre',
            ),
        ),
    ]
