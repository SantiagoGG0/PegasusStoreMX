"""Llena Product.display_name con el nombre de Dropi limpio (ver
catalog/services/naming.py): sin la palabra cortada por el límite de 40
caracteres, sin "DROPI CUP" ni emojis y con mayúsculas normales.

Por defecto solo llena los vacíos, así no pisa un nombre editado a mano en
el admin. Usa bulk_update para no tocar last_synced (lastmod del sitemap).

    python manage.py clean_product_names --dry-run   # muestra ejemplos
    python manage.py clean_product_names
    python manage.py clean_product_names --refresh   # recalcula todos
"""
from django.core.management.base import BaseCommand

from catalog.models import Product
from catalog.services.naming import build_vocabulary, clean_display_name

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Llena display_name (nombre visible limpio) de los productos."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe; muestra cuántos cambian y ejemplos.")
        parser.add_argument("--refresh", action="store_true", help="Recalcula también los que ya tienen display_name.")

    def handle(self, *args, **opts):
        vocab = build_vocabulary(Product.objects.values_list("name", flat=True).iterator(chunk_size=5000))
        qs = Product.objects.only("pk", "name", "display_name")
        if not opts["refresh"]:
            qs = qs.filter(display_name="")

        changed, examples = [], []
        for product in qs.iterator(chunk_size=2000):
            cleaned = clean_display_name(product.name, vocab)
            if cleaned and cleaned != product.display_name:
                if len(examples) < 25 and cleaned != product.name:
                    examples.append((product.name, cleaned))
                product.display_name = cleaned
                changed.append(product)

        for before, after in examples:
            self.stdout.write(f"  {before!r} → {after!r}")
        self.stdout.write(f"Productos con nombre visible nuevo: {len(changed)}")
        if opts["dry_run"]:
            self.stdout.write("Simulación: no se cambió nada.")
            return
        for i in range(0, len(changed), BATCH_SIZE):
            Product.objects.bulk_update(changed[i:i + BATCH_SIZE], ["display_name"])
        self.stdout.write(self.style.SUCCESS("OK: nombres visibles guardados."))
