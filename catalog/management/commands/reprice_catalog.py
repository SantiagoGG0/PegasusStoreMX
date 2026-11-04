"""
Management command: reprice_catalog

Recalcula precio, estado de precio (envío gratis / envío pagado / bajo
margen) y puntaje de relevancia de todo el catálogo con
catalog/services/pricing.py y ranking.py. Por defecto solo simula y muestra
el impacto por categoría; --apply escribe. Nunca despublica productos.

Necesita el precio sugerido de Dropi (suggested_price), que llenan
`sync_stock` y `sync_galleries`. Los productos sin sugerido se saltan salvo
--allow-no-suggested (sin sugerido no hay tope de mercado).

Nunca toca productos con price_locked=True.

Usage:
    python manage.py reprice_catalog                    # simulación
    python manage.py reprice_catalog --category belleza
    python manage.py reprice_catalog --apply
    python manage.py reprice_catalog --rank-only --apply   # solo recalcula el ranking
"""
import statistics
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Product
from catalog.services.pricing import (
    STATUS_FREE_SHIPPING,
    STATUS_LOW_MARGIN,
    STATUS_PAID_SHIPPING,
    category_key,
    compute_price,
)
from catalog.services.ranking import compute_rank_score

BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Recalcula precios (modelo híbrido de envío, tope de mercado, redondeo ...900) y ranking. Simulación por defecto."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe los cambios en la DB.")
        parser.add_argument("--category", default="", help="Solo esta categoría (ej. belleza).")
        parser.add_argument("--include-inactive", action="store_true", help="Incluye productos inactivos.")
        parser.add_argument("--allow-no-suggested", action="store_true", help="Recalcula también productos sin precio sugerido.")
        parser.add_argument("--rank-only", action="store_true", help="No cambia precios, solo el puntaje de relevancia.")

    def handle(self, *args, **opts):
        qs = Product.objects.select_related("category")
        if not opts["include_inactive"]:
            qs = qs.filter(is_active=True)
        if opts["category"]:
            qs = qs.filter(category__dropi_id=f"store:{opts['category']}")

        report = defaultdict(lambda: {
            "n": 0, "up": 0, "down": 0, "same": 0, "deltas": [], "skipped": 0,
            STATUS_FREE_SHIPPING: 0, STATUS_PAID_SHIPPING: 0, STATUS_LOW_MARGIN: 0,
        })
        changed = []
        now = timezone.now()

        for product in qs.iterator(chunk_size=2000):
            row = report[category_key(product.category) or "sin_categoria"]
            row["n"] += 1
            fields = set()

            can_price = not opts["rank_only"] and not product.price_locked
            if can_price and not product.suggested_price and not opts["allow_no_suggested"]:
                row["skipped"] += 1
                can_price = False
            if can_price:
                decision = compute_price(product.cost, product.suggested_price, product.category)
                if decision.status in row:
                    row[decision.status] += 1
                if product.price and decision.price != product.price:
                    row["deltas"].append(float((decision.price - product.price) / product.price))
                    row["up" if decision.price > product.price else "down"] += 1
                else:
                    row["same"] += 1
                if decision.price != product.price:
                    product.price = decision.price
                    product.last_synced = now
                    fields |= {"price", "last_synced"}
                if decision.status != product.pricing_status:
                    product.pricing_status = decision.status
                    fields.add("pricing_status")

            score = compute_rank_score(product)
            if score != product.rank_score:
                product.rank_score = score
                fields.add("rank_score")
            if fields:
                changed.append((product, fields))

        self._print_report(report)

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING(f"\nSimulación: {len(changed)} productos cambiarían. Usa --apply para guardar."))
            return

        by_fields = defaultdict(list)
        for product, fields in changed:
            by_fields[frozenset(fields)].append(product)
        for fields, products in by_fields.items():
            for i in range(0, len(products), BATCH_SIZE):
                Product.objects.bulk_update(products[i:i + BATCH_SIZE], list(fields))
        self.stdout.write(self.style.SUCCESS(f"\nOK: {len(changed)} productos actualizados."))

    def _print_report(self, report):
        self.stdout.write(
            f"{'categoría':<18}{'productos':>10}{'suben':>7}{'bajan':>7}{'igual':>7}{'Δ mediana':>11}"
            f"{'env.gratis':>11}{'env.pagado':>11}{'bajo marg.':>11}{'sin sug.':>9}"
        )
        totals = defaultdict(int)
        for key, row in sorted(report.items(), key=lambda kv: -kv[1]["n"]):
            median = f"{statistics.median(row['deltas']) * 100:+.0f}%" if row["deltas"] else "-"
            self.stdout.write(
                f"{key:<18}{row['n']:>10}{row['up']:>7}{row['down']:>7}{row['same']:>7}{median:>11}"
                f"{row[STATUS_FREE_SHIPPING]:>11}{row[STATUS_PAID_SHIPPING]:>11}{row[STATUS_LOW_MARGIN]:>11}{row['skipped']:>9}"
            )
            for k in ("n", STATUS_FREE_SHIPPING, STATUS_PAID_SHIPPING, STATUS_LOW_MARGIN):
                totals[k] += row[k]
        self.stdout.write(
            f"\nTotal {totals['n']}: {totals[STATUS_FREE_SHIPPING]} con envío gratis, "
            f"{totals[STATUS_PAID_SHIPPING]} con envío pagado por el cliente, "
            f"{totals[STATUS_LOW_MARGIN]} con bajo margen (siguen publicados, bajan en el ranking)."
        )
