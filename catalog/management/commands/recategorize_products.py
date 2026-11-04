from django.core.management.base import BaseCommand

from catalog.models import Category
from catalog.models import Product
from catalog.services.categorization import (
    STORE_CATEGORY_PREFIX,
    classify_product_text,
    ensure_store_categories,
    store_category_dropi_id,
)


class Command(BaseCommand):
    help = "Recategoriza productos activos con la taxonomía curada de Pegasus."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra cambios sin guardar.")
        parser.add_argument("--include-locked", action="store_true", help="Incluye productos bloqueados manualmente.")
        parser.add_argument("--limit", type=int, default=0, help="Máximo de productos a procesar.")
        parser.add_argument("--quiet", action="store_true", help="No imprime cada producto cambiado.")
        parser.add_argument("--batch-size", type=int, default=500, help="Tamaño de lote para actualizar.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_locked = options["include_locked"]
        limit = options["limit"]
        quiet = options["quiet"]
        batch_size = options["batch_size"]

        qs = Product.objects.all().select_related("category").order_by("id")
        if not include_locked:
            qs = qs.filter(category_locked=False)

        categories_by_dropi_id = {
            category.dropi_id: category
            for category in (
                Category.objects.filter(dropi_id__startswith=STORE_CATEGORY_PREFIX)
                if dry_run
                else ensure_store_categories()
            )
        }
        processed = 0
        changed = 0
        last_pk = 0
        while True:
            remaining = limit - processed if limit else batch_size
            if remaining <= 0:
                break
            current_batch_size = min(batch_size, remaining)
            batch = list(qs.filter(pk__gt=last_pk)[:current_batch_size])
            if not batch:
                break

            updates = []
            for product in batch:
                last_pk = product.pk
                result = classify_product_text(
                    name=product.name,
                    description=product.description,
                    dropi_category_name=product.dropi_category_name,
                )
                target_dropi_id = store_category_dropi_id(result.category_key)
                category = categories_by_dropi_id.get(target_dropi_id)
                processed += 1
                category_changed = (
                    product.category.dropi_id if product.category_id else None
                ) != target_dropi_id
                will_change = (
                    category_changed
                    or product.category_confidence != result.confidence
                    or product.category_reason != result.reason
                )
                if not will_change:
                    continue
                changed += 1
                if not quiet:
                    category_name = category.name if category else result.label
                    self.stdout.write(
                        f"{product.dropi_id}: {product.name[:70]} -> {category_name} "
                        f"({result.confidence}%, {result.reason})"
                    )
                if category is not None:
                    product.category = category
                product.category_confidence = result.confidence
                product.category_reason = result.reason
                updates.append(product)

            if updates and not dry_run:
                Product.objects.bulk_update(
                    updates,
                    ["category", "category_confidence", "category_reason"],
                    batch_size=batch_size,
                )

        mode = "DRY RUN " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{mode}{processed} procesados, {changed} cambios."))
