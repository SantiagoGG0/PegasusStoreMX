from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_productimage_product_video_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='video_file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='products/videos/',
                verbose_name='Video (archivo)',
                help_text='Sube un archivo de video (.mp4, .webm). Tiene prioridad sobre el Video URL.',
            ),
        ),
    ]
