"""
Elimina productos duplicados por nombre.

Lógica:
- Agrupa productos por nombre normalizado (strip + lower).
- Por cada grupo con más de 1 producto:
    - Calcula ganancia = price - cost para cada uno.
    - Si la diferencia entre la mayor y menor ganancia es < PROFIT_DIFF_THRESHOLD
      del grupo → conserva el MÁS BARATO (menor price).
    - Si la diferencia es >= threshold → conserva el MÁS RENTABLE (mayor ganancia).
- Elimina todos los demás del grupo.

Uso:
    python manage.py dedup_products
    python manage.py dedup_products --dry-run       # sólo muestra, no borra
    python manage.py dedup_products --threshold 0.20
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count

from catalog.models import Product


PROFIT_DIFF_THRESHOLD = Decimal("0.15")  # 15 %


class Command(BaseCommand):
    help = "Elimina productos duplicados por nombre, conservando el más rentable o el más económico."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Muestra qué se borraría sin borrar nada.",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=float(PROFIT_DIFF_THRESHOLD),
            help="Umbral de diferencia de ganancia para preferir el más barato (default: 0.15 = 15%%).",
        )

    def handle(self, *args, **options):
        try:
            self.stdout._out.reconfigure(errors="replace")
        except AttributeError:
            pass
        dry_run: bool = options["dry_run"]
        threshold = Decimal(str(options["threshold"]))

        if dry_run:
            self.stdout.write(self.style.WARNING("-- DRY RUN: no se eliminará nada --"))

        # Nombres que aparecen más de una vez (normalizado)
        all_products = Product.objects.only("id", "dropi_id", "name", "price", "cost", "supplier_id")
        groups: dict[tuple, list] = {}
        for p in all_products:
            key = (p.name.strip().lower(), p.supplier_id)
            groups.setdefault(key, []).append(p)

        duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS("No se encontraron duplicados."))
            return

        total_deleted = 0
        total_groups = len(duplicate_groups)

        self.stdout.write(f"Grupos duplicados encontrados: {total_groups}\n")

        for (name_key, supplier_id), products in duplicate_groups.items():
            # Calcular ganancia por producto
            def profit(p):
                return p.price - p.cost

            max_profit = max(profit(p) for p in products)
            min_profit = min(profit(p) for p in products)

            profit_diff = max_profit - min_profit
            # Evitar división por cero
            if max_profit > 0:
                relative_diff = profit_diff / max_profit
            else:
                relative_diff = Decimal("0")

            # Decidir cuál conservar
            if relative_diff < threshold:
                # Diferencia pequena -> conservar el mas barato
                keeper = min(products, key=lambda p: p.price)
                reason = f"diff={relative_diff:.0%} < {threshold:.0%} -> mas economico"
            else:
                # Diferencia grande -> conservar el mas rentable
                keeper = max(products, key=profit)
                reason = f"diff={relative_diff:.0%} >= {threshold:.0%} -> mas rentable"

            to_delete = [p for p in products if p.id != keeper.id]

            self.stdout.write(
                f"\n[{name_key[:50]}] proveedor={supplier_id} {len(products)} duplicados — {reason}"
            )
            self.stdout.write(
                f"  CONSERVAR: id={keeper.dropi_id}  price=${keeper.price:,.0f}  ganancia=${profit(keeper):,.0f}"
            )
            for p in to_delete:
                self.stdout.write(
                    f"  BORRAR:    id={p.dropi_id}  price=${p.price:,.0f}  ganancia=${profit(p):,.0f}"
                )

            if not dry_run:
                ids_to_delete = [p.id for p in to_delete]
                Product.objects.filter(id__in=ids_to_delete).delete()
                total_deleted += len(ids_to_delete)

        if dry_run:
            estimated = sum(len(v) - 1 for v in duplicate_groups.values())
            self.stdout.write(
                self.style.WARNING(f"\nSe eliminarían {estimated} productos de {total_groups} grupos.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nEliminados {total_deleted} duplicados de {total_groups} grupos.")
            )
