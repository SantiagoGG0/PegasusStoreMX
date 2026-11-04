"""
Management command: rebalance_catalog

Ajusta qué se publica según el stock real de Dropi (lo que dejó `sync_stock`),
sin borrar nada:

  1. Despublica (inactive_reason="sin_stock") productos activos que tienen
     variantes pero ninguna con stock en ninguna bodega: se ven disponibles
     pero no se puede comprar ninguna opción.
  2. Republica productos inactivos sin motivo automático que hoy SÍ están en
     Dropi con stock (precio sugerido > 0), con imágenes, sin imagen marcada,
     sin exclusión SEO y que no son duplicados. Recupera los que despublicó la
     regla vieja de rentabilidad.

Simula por defecto; --apply escribe. Después correr `reprice_catalog --apply`
para que los republicados queden con el precio nuevo.

Usage:
    python manage.py rebalance_catalog
    python manage.py rebalance_catalog --apply
"""
from collections import Counter

from django.core.management.base import BaseCommand

from catalog.inventory import variation_stock
from catalog.models import Product

BATCH_SIZE = 500


def has_variants_without_stock(product) -> bool:
    """True si el producto tiene variantes con detalle de bodega y ninguna
    tiene stock (variantes del listado sin ese detalle no cuentan)."""
    variants = [
        v for v in (product.variants or [])
        if isinstance(v, dict) and "warehouse_product_variation" in v and v.get("id")
    ]
    return bool(variants) and all(variation_stock(product, v["id"]) <= 0 for v in variants)


class Command(BaseCommand):
    help = "Despublica activos sin variantes comprables y republica inactivos que hoy tienen stock en Dropi. Simulación por defecto."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe los cambios.")

    def handle(self, *args, **opts):
        to_deactivate = [
            p for p in Product.objects.filter(is_active=True).only("id", "variants", "stock", "category_id").select_related("category")
            if has_variants_without_stock(p)
        ]
        candidates = (
            Product.objects.filter(
                is_active=False, inactive_reason="", stock__gt=0, suggested_price__gt=0,
                image_flagged=False, seo_exclusion="", canonical_product__isnull=True,
            )
            .exclude(images=[])
            .select_related("category")
            .only("id", "variants", "stock", "category__name")
        )
        to_reactivate = [p for p in candidates if not has_variants_without_stock(p)]

        self.stdout.write(f"Activos sin ninguna variante comprable (se despublican): {len(to_deactivate)}")
        self.stdout.write(f"Inactivos con stock hoy en Dropi (se republican):       {len(to_reactivate)}")
        for name, n in Counter(p.category.name if p.category else "-" for p in to_reactivate).most_common(8):
            self.stdout.write(f"    {name:<24}{n:>6}")

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("Simulación: no se cambió nada. Usa --apply."))
            return

        for p in to_deactivate:
            p.is_active, p.inactive_reason = False, "sin_stock"
        for p in to_reactivate:
            p.is_active, p.inactive_reason = True, ""
        changed = to_deactivate + to_reactivate
        for i in range(0, len(changed), BATCH_SIZE):
            Product.objects.bulk_update(changed[i:i + BATCH_SIZE], ["is_active", "inactive_reason"])
        self.stdout.write(self.style.SUCCESS(
            f"OK: {len(to_deactivate)} despublicados, {len(to_reactivate)} republicados. "
            "Siguiente paso: reprice_catalog --apply."
        ))
