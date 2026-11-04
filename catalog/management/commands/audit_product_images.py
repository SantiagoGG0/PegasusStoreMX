"""
Management command: audit_product_images

Reports how many products have 0, 1, 2 or 3+ images, broken down by active
status and category. Read-only — used to size the image backfill work
(catalog.services.image_generation / backfill_product_images).

Usage:
    python manage.py audit_product_images
    python manage.py audit_product_images --active-only
    python manage.py audit_product_images --by-category
"""
from collections import Counter

from django.core.management.base import BaseCommand

from catalog.models import Product


def _bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


class Command(BaseCommand):
    help = "Audita cuantas imagenes (Dropi + custom) tiene cada producto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Solo cuenta productos con is_active=True.",
        )
        parser.add_argument(
            "--by-category",
            action="store_true",
            help="Desglosa los totales por categoria.",
        )

    def handle(self, *args, **options):
        active_only = options["active_only"]
        by_category = options["by_category"]

        qs = Product.objects.select_related("category").prefetch_related("custom_images")
        if active_only:
            qs = qs.filter(is_active=True)

        overall: Counter[str] = Counter()
        per_category: dict[str, Counter[str]] = {}
        total = 0

        for product in qs.iterator(chunk_size=1000):
            custom_count = len(product.custom_images.all())
            image_count = custom_count if custom_count else len(product.images or [])
            bucket = _bucket(image_count)

            overall[bucket] += 1
            total += 1

            if by_category:
                cat_name = product.category.name if product.category else "(sin categoría)"
                per_category.setdefault(cat_name, Counter())[bucket] += 1

        self.stdout.write(f"Total productos escaneados: {total}"
                           + (" (solo activos)" if active_only else ""))
        self.stdout.write("")
        for bucket in ("0", "1", "2", "3+"):
            count = overall.get(bucket, 0)
            pct = (count / total * 100) if total else 0
            label = "sin imágenes" if bucket == "0" else f"{bucket} imagen(es)"
            self.stdout.write(f"  {label:<16}: {count:>6}  ({pct:5.1f}%)")

        if by_category:
            self.stdout.write("\nPor categoría:")
            for cat_name, counts in sorted(per_category.items(), key=lambda kv: -sum(kv[1].values())):
                cat_total = sum(counts.values())
                zero = counts.get("0", 0)
                one = counts.get("1", 0)
                self.stdout.write(
                    f"  {cat_name[:40]:<40} total={cat_total:>5}  0img={zero:>5}  1img={one:>5}"
                )
