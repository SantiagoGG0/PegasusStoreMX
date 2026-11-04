from django.db import migrations


class Migration(migrations.Migration):
    """Drops the search_vector column/index left over from
    0014_add_search_vector_and_unaccent. Product search has run entirely on
    a runtime SearchVector('name', ...) annotation (see catalog/views.py)
    since before this repo's migration history was traced — this column was
    never read anywhere and 0015's comment already noted it predated that
    change. Unrelated to the ShippingExperimentEvent model added right
    after this migration; split out so it can be reviewed/rolled back on
    its own."""

    dependencies = [
        ('catalog', '0015_remove_product_catalog_product_search_idx_and_more'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='product',
            name='catalog_product_search_idx',
        ),
        migrations.RemoveField(
            model_name='product',
            name='search_vector',
        ),
    ]
