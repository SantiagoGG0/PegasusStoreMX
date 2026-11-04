"""
Management command: sync_stock

Bulk-syncs stock, cost and variants for locally-imported products from Dropi
using a single paginated crawl of products/index (see
catalog.services.stock_sync), instead of one HTTP request per local product.
Dropi returns at most 40 products per page and tolerates ~6 requests/min,
so a full-catalog refresh (~46k products, ~1,150 pages) takes ~4 hours. It
runs every 2-3 days from scripts/sync_catalog.ps1.

Usage:
    python manage.py sync_stock
    python manage.py sync_stock --deactivate-zero   # sets is_active=False when stock=0
    python manage.py sync_stock --reactivate         # sets is_active=True when stock>0 again
    python manage.py sync_stock --dry-run
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Product
from catalog.services.stock_sync import apply_listing_raw, fetch_active_catalog_map, touches_page

logger = logging.getLogger(__name__)

BULK_UPDATE_BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Sync masivo de stock/cost/variantes de productos locales con Dropi (paginado, sin 1 request por producto)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--deactivate-zero",
            action="store_true",
            default=False,
            help="Set is_active=False para productos cuyo stock cae a 0.",
        )
        parser.add_argument(
            "--reactivate",
            action="store_true",
            default=False,
            help="Set is_active=True para productos inactivos cuyo stock volvió a ser > 0.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="No escribe en la DB, solo reporta lo que cambiaría.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=10.0,
            metavar="SECS",
            help="Pausa entre páginas de la API. Default: 10 (Dropi bloquea por encima de ~6 requests/min)",
        )

    def handle(self, *args, **options):
        deactivate_zero = options["deactivate_zero"]
        reactivate = options["reactivate"]
        dry_run = options["dry_run"]
        delay = options["delay"]

        self.stdout.write("Descargando catálogo activo de Dropi (paginado)...")
        catalog_map = fetch_active_catalog_map(delay=delay, stdout=self.stdout)
        self.stdout.write(f"  {len(catalog_map)} productos encontrados en Dropi.\n")

        local_products = list(Product.objects.select_related("category"))
        total = len(local_products)

        # Protección: si el recorrido trajo muy pocos productos (Dropi cortó,
        # rate limit, cambio en la API), no se despublica nada por "ya no
        # existe": sería despublicar el catálogo entero por un fallo de red.
        active_local = sum(1 for p in local_products if p.is_active)
        found_local = sum(1 for p in local_products if p.dropi_id in catalog_map)
        crawl_ok = active_local == 0 or found_local >= 0.5 * active_local
        if deactivate_zero and not crawl_ok:
            self.stdout.write(self.style.ERROR(
                f"  Recorrido incompleto: Dropi devolvió {found_local} de {active_local} productos activos. "
                "No se despublica nada por 'ya no existe' en esta corrida."
            ))
        self.stdout.write(f"Comparando contra {total} productos locales...")

        to_update = []
        updated = 0
        deactivated = 0
        reactivated = 0
        vanished = 0
        repriced = 0
        now = timezone.now()

        for product in local_products:
            raw = catalog_map.get(product.dropi_id)
            changed = set()

            if raw is None:
                # Product no longer returned by Dropi's active catalog
                if deactivate_zero and crawl_ok and product.is_active:
                    product.is_active = False
                    product.inactive_reason = "no_existe"
                    changed |= {"is_active", "inactive_reason"}
                    vanished += 1
            else:
                changed, events = apply_listing_raw(
                    product, raw, deactivate_zero=deactivate_zero, reactivate=reactivate
                )
                deactivated += "deactivated" in events
                reactivated += "reactivated" in events
                repriced += "repriced" in events

            if changed:
                if touches_page(changed):
                    product.last_synced = now
                    changed.add("last_synced")
                to_update.append((product, changed))
                updated += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n[DRY RUN] {updated}/{total} productos cambiarían "
                f"({deactivated} desactivados, {reactivated} reactivados, {vanished} desaparecidos de Dropi, "
                f"{repriced} con precio recalculado por cambio de costo)."
            ))
            return

        # Group by the exact set of changed fields so bulk_update gets a
        # consistent field list per batch.
        by_fields: dict[frozenset, list] = {}
        for product, changed in to_update:
            by_fields.setdefault(frozenset(changed), []).append(product)

        for fields, products in by_fields.items():
            field_list = list(fields)
            for i in range(0, len(products), BULK_UPDATE_BATCH_SIZE):
                Product.objects.bulk_update(products[i:i + BULK_UPDATE_BATCH_SIZE], field_list)

        self.stdout.write(self.style.SUCCESS(
            f"\nOK: sync completado — {updated}/{total} actualizados"
            + (f", {deactivated} desactivados" if deactivated else "")
            + (f", {reactivated} reactivados" if reactivated else "")
            + (f", {vanished} desaparecidos de Dropi" if vanished else "")
            + (f", {repriced} con precio recalculado" if repriced else "")
        ))

