from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_image_flagged'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='video_url',
            field=models.URLField(
                blank=True,
                verbose_name='Video URL',
                help_text='URL de YouTube, Vimeo o video directo (.mp4). Se muestra en la galería del producto.',
            ),
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='products/', verbose_name='Imagen')),
                ('order', models.PositiveSmallIntegerField(
                    default=0,
                    verbose_name='Orden',
                    help_text='Menor número = aparece primero.',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='custom_images',
                    to='catalog.product',
                    verbose_name='Producto',
                )),
            ],
            options={
                'verbose_name': 'Imagen personalizada',
                'verbose_name_plural': 'Imágenes personalizadas',
                'ordering': ['order', 'pk'],
            },
        ),
    ]
