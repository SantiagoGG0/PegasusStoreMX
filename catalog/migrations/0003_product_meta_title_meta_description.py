from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_product_seo_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='meta_description',
            field=models.CharField(
                blank=True,
                help_text='Descripción para motores de búsqueda. Máx. 160 caracteres.',
                max_length=160,
                verbose_name='Meta description (SEO)',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='meta_title',
            field=models.CharField(
                blank=True,
                help_text='Título para motores de búsqueda. Máx. 70 caracteres. Si está vacío se usa el nombre del producto.',
                max_length=70,
                verbose_name='Meta title (SEO)',
            ),
        ),
    ]
