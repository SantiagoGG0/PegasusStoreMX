from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0012_product_video_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductVideo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(
                    upload_to='products/videos/',
                    verbose_name='Archivo de video',
                    help_text='Formatos soportados: .mp4, .webm. Se reproduce automáticamente en la galería.',
                )),
                ('order', models.PositiveSmallIntegerField(
                    default=0,
                    verbose_name='Orden',
                    help_text='Menor número = aparece primero.',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='custom_videos',
                    to='catalog.product',
                    verbose_name='Producto',
                )),
            ],
            options={
                'verbose_name': 'Video personalizado',
                'verbose_name_plural': 'Videos personalizados',
                'ordering': ['order', 'pk'],
            },
        ),
    ]
