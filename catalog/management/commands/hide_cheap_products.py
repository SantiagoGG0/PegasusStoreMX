"""
Management command: hide_cheap_products

Despublica (inactive_reason="precio_bajo", nunca borra) los productos activos
cuyo precio quedó por debajo de settings.CATALOG_MIN_PRICE: un borrador de
$1.900 no se vende solo porque la guía cuesta diez veces más, y un "$900" en
la vitrina parece un error. sync_stock y sync_galleries no los reactivan
(precio_bajo no es un motivo automático).

Correr después de `reprice_catalog --apply`, para juzgar el precio ya
corregido, y reponer la cantidad con `import_products` (el catálogo no se
achica).

Usage:
    python manage.py hide_cheap_products            # simulación
    python manage.py hide_cheap_products --apply
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from catalog.models import Product


class Command(BaseCommand):
    help = "Despublica productos con precio por debajo de CATALOG_MIN_PRICE. Simulación por defecto."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe los cambios en la DB.")

    def handle(self, *args, **opts):
        from catalog.services.seo_consolidation import protected_product_ids

        # Nunca se ocultan productos vendidos ni fichas con tráfico orgánico
        # (data/seo_protected_slugs.txt): su página daría 410 y se perdería.
        qs = Product.objects.filter(is_active=True, price__lt=settings.CATALOG_MIN_PRICE, price_locked=False).exclude(
            pk__in=protected_product_ids()
        )
        total = qs.count()
        for p in qs.order_by("price")[:15]:
            self.stdout.write(f"  #{p.pk} ${p.price:,.0f} (costo ${p.cost:,.0f}) {p.name[:60]}")
        if not opts["apply"]:
            self.stdout.write(self.style.WARNING(
                f"Simulación: {total} productos por debajo de ${settings.CATALOG_MIN_PRICE:,} se ocultarían. Usa --apply."
            ))
            return
        updated = qs.update(is_active=False, inactive_reason="precio_bajo")
        self.stdout.write(self.style.SUCCESS(
            f"OK: {updated} productos ocultos. Repón la cantidad con import_products --limit {updated}."
        ))
