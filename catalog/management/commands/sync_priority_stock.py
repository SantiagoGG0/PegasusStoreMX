"""
Management command: sync_priority_stock

Pone al día el stock solo de los productos que más importan: los vendidos
(algún pedido) y las fichas con tráfico orgánico (data/seo_protected_slugs.txt).
Son unos cientos, no 46.000, así que con el detalle de Dropi (products/v2/{id})
termina en minutos y cabe a diario en GitHub Actions; el recorrido completo de
sync_stock tarda ~4 h.

Ejemplo de por qué existe: la ficha con más clics de Google (Selvia Ajenjo)
pasó 10 días como "Agotado" con 451 unidades en Dropi, porque el sync completo
dejó de correr al quitar la tarea del PC.

Solo toca stock y la reactivación:
- Nunca despublica: con stock 0 la ficha sigue en línea como agotada (un 410
  perdería el posicionamiento); despublicar es trabajo de sync_stock.
- Reactiva lo que despublicó un sync automático (sin_stock, no_existe) si Dropi
  lo tiene activo, no privado y con stock.
- No cambia variantes ni costo: el detalle trae otra forma de variantes que
  el listado, que es lo que esperan la ficha y el checkout.

Reparte las consultas entre los tokens de settings.DROPI_READ_TOKENS (Dropi
limita ~6 requests/min por token).

Usage:
    python manage.py sync_priority_stock --dry-run
    python manage.py sync_priority_stock
    python manage.py sync_priority_stock --max-minutes 20
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Product
from catalog.services.dropi_import import parse_stock
from catalog.services.stock_sync import touches_page
from dropi_client import DropiAPIError, DropiClient

AUTO_INACTIVE_REASONS = ("sin_stock", "no_existe")
MAX_ATTEMPTS = 4
RATE_LIMIT_SLEEP = 30  # primera espera tras un 429; se duplica en cada reintento


def apply_detail(product, raw: dict) -> set:
    """Aplica a `product` el detalle de Dropi (stock y reactivación). No guarda."""
    changed = set()
    new_stock = parse_stock(raw)
    if product.stock != new_stock:
        product.stock = new_stock
        changed.add("stock")
    sellable = bool(raw.get("active")) and not raw.get("privated_product")
    if (
        sellable and new_stock > 0 and not product.is_active
        and product.inactive_reason in AUTO_INACTIVE_REASONS
    ):
        product.is_active = True
        product.inactive_reason = ""
        changed |= {"is_active", "inactive_reason"}
    return changed


class Command(BaseCommand):
    help = "Stock al día de los productos vendidos y con tráfico orgánico (detalle de Dropi, varios tokens)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe en la DB, solo reporta.")
        parser.add_argument(
            "--delay", type=float, default=12.0, metavar="SECS",
            help="Espaciado mínimo entre requests de un mismo token. Default: 12 (Dropi aguanta ~6/min).",
        )
        parser.add_argument("--max-minutes", type=float, default=0, help="Corta al pasar N minutos (0 = sin límite).")

    def handle(self, *args, **opts):
        from catalog.services.seo_consolidation import protected_product_ids

        products = list(
            Product.objects.filter(pk__in=protected_product_ids()).select_related("category").order_by("-rank_score")
        )
        tokens = [t for t in settings.DROPI_READ_TOKENS if t]
        clients = [DropiClient(t) for t in tokens]
        last_call = [0.0] * len(clients)
        deadline = time.monotonic() + opts["max_minutes"] * 60 if opts["max_minutes"] else None
        self.stdout.write(f"{len(products)} productos prioritarios, {len(clients)} token(s).")

        now = timezone.now()
        stats = {"checked": 0, "updated": 0, "reactivated": 0, "errors": 0}
        for i, product in enumerate(products):
            if deadline and time.monotonic() > deadline:
                self.stdout.write(self.style.WARNING(f"  Límite de tiempo: quedaron {len(products) - i} sin revisar."))
                break
            slot = i % len(clients)
            raw = None
            for attempt in range(MAX_ATTEMPTS):
                wait = opts["delay"] - (time.monotonic() - last_call[slot])
                if wait > 0:
                    time.sleep(wait)
                last_call[slot] = time.monotonic()
                try:
                    raw = clients[slot].get_product(product.dropi_id, timeout=30).get("objects") or {}
                    break
                except DropiAPIError as exc:
                    if "429" not in str(exc) or attempt == MAX_ATTEMPTS - 1:
                        self.stdout.write(f"  #{product.pk} {product.slug}: error de Dropi ({str(exc)[:100]})")
                        break
                    # El sitio en vivo comparte el token principal: se espera y se reintenta el mismo.
                    time.sleep(RATE_LIMIT_SLEEP * 2 ** attempt)
            if raw is None:
                stats["errors"] += 1
                continue
            stats["checked"] += 1
            if not isinstance(raw, dict) or not raw:
                continue

            before = product.stock
            changed = apply_detail(product, raw)
            if not changed:
                continue
            stats["updated"] += 1
            stats["reactivated"] += "is_active" in changed
            self.stdout.write(
                f"  #{product.pk} {product.slug}: stock {before} → {product.stock}"
                + (" (reactivado)" if "is_active" in changed else "")
            )
            if opts["dry_run"]:
                continue
            if touches_page(changed):
                product.last_synced = now
                changed.add("last_synced")
            product.save(update_fields=sorted(changed))

        prefix = "[DRY RUN] " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{stats['checked']} revisados, {stats['updated']} con cambios "
            f"({stats['reactivated']} reactivados), {stats['errors']} errores de Dropi."
        ))
