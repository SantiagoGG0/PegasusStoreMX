"""Recalcula los productos de las colecciones y, con --load-seed, crea las
colecciones iniciales de catalog/data/collections_seed.py.

    python manage.py refresh_collections --load-seed --dry-run   # solo cuenta
    python manage.py refresh_collections --load-seed             # crea y publica
    python manage.py refresh_collections                         # solo recalcula

Al crear, publica solo las colecciones con al menos MIN_PRODUCTS_TO_PUBLISH
productos; las demás quedan como borrador en el admin. No pisa lo editado en
el admin salvo con --overwrite-seed.
"""
from django.core.management.base import BaseCommand, CommandError

from catalog.models import Category, Collection
from catalog.services.collections import (
    MIN_PRODUCTS_TO_PUBLISH,
    compile_matcher,
    eligible_products,
    refresh_collections,
)
from catalog.services.categorization import store_category_dropi_id


class Command(BaseCommand):
    help = "Recalcula los productos de las colecciones (y carga las iniciales con --load-seed)."

    def add_arguments(self, parser):
        parser.add_argument("--load-seed", action="store_true", help="Crea las colecciones iniciales que no existan.")
        parser.add_argument("--overwrite-seed", action="store_true", help="Reemplaza textos y términos con los del archivo.")
        parser.add_argument("--dry-run", action="store_true", help="Solo muestra cuántos productos tendría cada una.")

    def handle(self, *args, **opts):
        from catalog.data.collections_seed import SEED

        if opts["dry_run"]:
            rows = list(eligible_products().values_list("name", "display_name"))
            for item in SEED:
                matches = compile_matcher("\n".join(item["include"]), "\n".join(item["exclude"]))
                n = sum(1 for name, shown in rows if matches(name) or (shown and matches(shown)))
                flag = "" if n >= MIN_PRODUCTS_TO_PUBLISH else "  (borrador: muy pocos)"
                self.stdout.write(f"{n:6d}  {item['category']}/{item['slug']}{flag}")
            self.stdout.write("Simulación: no se cambió nada.")
            return

        created = []
        if opts["load_seed"]:
            for position, item in enumerate(SEED, start=1):
                category = Category.objects.filter(dropi_id=store_category_dropi_id(item["category"])).first()
                if category is None:
                    raise CommandError(f"No existe la categoría {item['category']}")
                fields = {
                    "name": item["name"],
                    "intro": item["intro"],
                    "faq": [{"q": q, "a": a} for q, a in item["faq"]],
                    "include_terms": "\n".join(item["include"]),
                    "exclude_terms": "\n".join(item["exclude"]),
                    "position": position,
                }
                collection, is_new = Collection.objects.get_or_create(category=category, slug=item["slug"], defaults=fields)
                if is_new:
                    created.append(collection)
                elif opts["overwrite_seed"]:
                    for key, value in fields.items():
                        setattr(collection, key, value)
                    collection.save()

        counts = refresh_collections()
        published = 0
        for collection in created:
            collection.refresh_from_db()
            if collection.product_count >= MIN_PRODUCTS_TO_PUBLISH:
                collection.is_published = True
                collection.save(update_fields=["is_published"])
                published += 1
        for collection in Collection.objects.select_related("category").order_by("category__name", "position"):
            state = "publicada" if collection.is_published else "borrador"
            self.stdout.write(f"{counts.get(collection.pk, 0):6d}  {collection.get_absolute_url()}  ({state})")
        self.stdout.write(self.style.SUCCESS(f"OK: {len(counts)} colecciones recalculadas, {len(created)} nuevas, {published} publicadas."))
