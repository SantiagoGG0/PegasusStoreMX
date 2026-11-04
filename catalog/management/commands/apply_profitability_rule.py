"""
Management command: apply_profitability_rule

Recorre el catálogo local y evalúa Product.profitability_status (3 reglas —
ver catalog/models.py):

  1. needs_combo   — el cargo de envío en checkout supera settings.SHIPPING_CEILING.
                      Nunca se despublica automático; requiere combo manual
                      (ver catalog/services/combo_suggestions.py y el admin).
  2. profitable    — bajo el techo, con ganancia neta esperada (ya descuenta
                      rechazo COD) Y margen % por encima de los umbrales.
  3. unprofitable  — bajo el techo, pero no cumple ganancia neta y/o margen %.
                      Único candidato real a --deactivate-unprofitable.

Por defecto solo reporta; no toca la base de datos a menos que se pase
--deactivate-unprofitable o --reactivate-profitable. No borra nada: los
productos despublicados quedan con is_active=False (fuera de sitemap,
listados y búsqueda) pero siguen en la base de datos y se siguen
sincronizando con Dropi.

Usage:
    python manage.py apply_profitability_rule                        # solo reporta
    python manage.py apply_profitability_rule --show-demand           # + cuántos "sin margen" tienen historial de pedidos
    python manage.py apply_profitability_rule --deactivate-unprofitable
    python manage.py apply_profitability_rule --reactivate-profitable
"""

from django.core.management.base import BaseCommand

from catalog.models import Product

BULK_UPDATE_BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Evalúa las 3 reglas de rentabilidad (techo de envío / margen pesos+% / combo) y opcionalmente despublica/republica según corresponda."

    def add_arguments(self, parser):
        parser.add_argument(
            "--deactivate-unprofitable",
            action="store_true",
            default=False,
            help="Set is_active=False para productos activos 'sin margen' (bajo el techo). Nunca toca needs_combo.",
        )
        parser.add_argument(
            "--reactivate-profitable",
            action="store_true",
            default=False,
            help="Set is_active=True para productos inactivos que sí son rentables (no reactiva needs_combo ni image_flagged).",
        )
        parser.add_argument(
            "--show-demand",
            action="store_true",
            default=False,
            help="Cruza el bucket 'sin margen y activos' contra el historial de Order.items — cuántos ya tienen al menos un pedido.",
        )

    def handle(self, *args, **options):
        deactivate = options["deactivate_unprofitable"]
        reactivate = options["reactivate_profitable"]
        show_demand = options["show_demand"]

        products = list(Product.objects.only("id", "dropi_id", "price", "cost", "is_active", "image_flagged"))
        total = len(products)

        buckets = {
            ("profitable", True): [],
            ("profitable", False): [],
            ("needs_combo", True): [],
            ("needs_combo", False): [],
            ("unprofitable", True): [],
            ("unprofitable", False): [],
        }
        for p in products:
            buckets[(p.profitability_status, p.is_active)].append(p)

        self.stdout.write(f"Catálogo evaluado: {total} productos.\n")
        self.stdout.write(f"  Rentables y activos:                {len(buckets[('profitable', True)])}")
        self.stdout.write(f"  Rentables pero inactivos:           {len(buckets[('profitable', False)])}")
        self.stdout.write(f"  Necesitan combo y activos:          {len(buckets[('needs_combo', True)])}  (nunca se despublican solos)")
        self.stdout.write(f"  Necesitan combo e inactivos:        {len(buckets[('needs_combo', False)])}")
        self.stdout.write(f"  Sin margen y activos:               {len(buckets[('unprofitable', True)])}  (candidatos a --deactivate-unprofitable)")
        self.stdout.write(f"  Sin margen e inactivos:             {len(buckets[('unprofitable', False)])}\n")

        if show_demand:
            self._show_demand(buckets[("unprofitable", True)])

        if not deactivate and not reactivate:
            self.stdout.write(self.style.WARNING(
                "Solo diagnóstico — no se modificó nada. "
                "Usa --deactivate-unprofitable y/o --reactivate-profitable para aplicar cambios."
            ))
            return

        to_deactivate = buckets[("unprofitable", True)] if deactivate else []
        to_reactivate = (
            [p for p in buckets[("profitable", False)] if not p.image_flagged]
            if reactivate else []
        )

        if to_deactivate:
            for p in to_deactivate:
                p.is_active = False
            for i in range(0, len(to_deactivate), BULK_UPDATE_BATCH_SIZE):
                Product.objects.bulk_update(to_deactivate[i:i + BULK_UPDATE_BATCH_SIZE], ["is_active"])
            self.stdout.write(self.style.SUCCESS(f"✓ {len(to_deactivate)} producto(s) despublicado(s) (sin margen, bajo el techo)."))

        if to_reactivate:
            for p in to_reactivate:
                p.is_active = True
            for i in range(0, len(to_reactivate), BULK_UPDATE_BATCH_SIZE):
                Product.objects.bulk_update(to_reactivate[i:i + BULK_UPDATE_BATCH_SIZE], ["is_active"])
            self.stdout.write(self.style.SUCCESS(f"✓ {len(to_reactivate)} producto(s) republicado(s) (rentables)."))

    def _show_demand(self, unprofitable_active: list) -> None:
        """Cuántos productos 'sin margen y activos' ya aparecieron en algún
        pedido (cualquier estado — un rechazo también cuenta como demanda
        real, alguien sí quiso comprarlo)."""
        from orders.models import Order

        ordered_dropi_ids: set[int] = set()
        ordered_local_ids: set[int] = set()
        for items in Order.objects.values_list("items", flat=True):
            if not items:
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                did = it.get("dropi_id") or it.get("id")
                if did is not None:
                    try:
                        ordered_dropi_ids.add(int(did))
                    except (TypeError, ValueError):
                        pass
                pid = it.get("product_id") or it.get("local_id")
                if pid is not None:
                    try:
                        ordered_local_ids.add(int(pid))
                    except (TypeError, ValueError):
                        pass

        with_demand = [
            p for p in unprofitable_active
            if p.pk in ordered_local_ids or getattr(p, "dropi_id", None) in ordered_dropi_ids
        ]
        self.stdout.write(
            f"Con historial de pedidos (cualquier estado) entre los 'sin margen y activos': "
            f"{len(with_demand)}/{len(unprofitable_active)}\n"
        )
