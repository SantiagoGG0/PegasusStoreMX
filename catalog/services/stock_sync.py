"""
Bulk stock/cost sync from Dropi.

Fetches the FULL active Dropi catalog via paginated `products/index` requests
(same technique as `import_products`'s `_fetch_page_with_stockmayor`), instead
of issuing one HTTP request per local product. This turns a full-catalog stock
refresh (~46k products) from ~46k sequential requests into a few hundred
paginated requests, making it fast enough to run every 30-60 minutes.
"""
import functools
import logging
import time
from decimal import Decimal

from dropi_client import DropiAPIError, DropiClient

from .dropi_import import parse_stock

logger = logging.getLogger(__name__)

PAGE_SIZE = 40  # Dropi never returns more than 40 per page
MAX_RETRIES = 6
RETRY_BACKOFF = 5      # seconds between retries
RATE_LIMIT_SLEEP = 30  # first sleep on a 429; doubles on each consecutive 429


def extract_stock(raw: dict) -> int:
    """Sum stock across warehouses/variants for a raw Dropi product dict."""
    return parse_stock(raw)


def extract_cost(raw: dict) -> float | None:
    """Same cost formula used at import time: sale_price, falling back to cost."""
    cost_raw = raw.get("sale_price") or raw.get("cost") or 0
    try:
        return float(cost_raw)
    except (TypeError, ValueError):
        return None


def extract_variants(raw: dict) -> list:
    return raw.get("variations") or raw.get("variants") or raw.get("attributes") or []


def _fetch_page(client: DropiClient, start_data: int, page_size: int, category: str, stdout=None) -> list:
    """
    Fetch one page from Dropi's products/index, injecting the real byte-offset
    (start_data) via a temporary monkey-patch on _post — Dropi's `page` param
    does not map 1:1 to `startData`, so we override it directly.
    No stockmayor pre-filter here: we want ALL products (including zero-stock
    ones) so we can also detect products that need deactivating.
    """
    original_post = client._post

    @functools.wraps(original_post)
    def patched_post(path, payload):
        if "products/index" in path:
            payload["startData"] = start_data
        return original_post(path, payload)

    client._post = patched_post
    rate_limited = 0
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.get_products(page=0, page_size=page_size, category=category)
                objects = resp.get("objects") or []
                if isinstance(objects, dict):
                    return objects.get("products") or objects.get("data") or []
                if isinstance(objects, list):
                    return objects
                return []
            except DropiAPIError as exc:
                msg = str(exc)
                # Never fall through to `return []` after exhausting retries:
                # an empty page means "end of catalog" to the caller, and
                # sync_stock --deactivate-zero would then deactivate every
                # product past this offset.
                if attempt == MAX_RETRIES:
                    raise
                if "429" in msg or "rate" in msg.lower():
                    pause = RATE_LIMIT_SLEEP * 2 ** rate_limited
                    rate_limited += 1
                    if stdout:
                        stdout.write(f"  Rate limit — esperando {pause}s...")
                    time.sleep(pause)
                else:
                    if stdout:
                        stdout.write(f"  Error API (intento {attempt}/{MAX_RETRIES}): {exc} — reintentando...")
                    time.sleep(RETRY_BACKOFF)
    finally:
        client._post = original_post
    return []


def fetch_active_catalog_map(category: str = "", page_size: int = PAGE_SIZE, delay: float = 10.0, stdout=None) -> dict:
    """
    Paginate through Dropi's products/index and return
    {dropi_id: raw_product_dict} for every product Dropi currently returns.

    One paginated crawl instead of one HTTP request per local product.
    """
    client = DropiClient()
    catalog: dict[int, dict] = {}
    start_data = 0
    pages = 0
    started = time.monotonic()

    while True:
        page_started = time.monotonic()
        products_list = _fetch_page(client, start_data, page_size, category, stdout)
        if not products_list:
            break
        pages += 1
        if stdout and pages % 10 == 0:
            minutes = (time.monotonic() - started) / 60
            stdout.write(
                f"  {time.strftime('%H:%M')}  página {pages}: {start_data + len(products_list)} productos "
                f"leídos en {minutes:.0f} min"
            )

        for raw in products_list:
            dropi_id = raw.get("id") or raw.get("products_id")
            if dropi_id:
                try:
                    catalog[int(dropi_id)] = raw
                except (TypeError, ValueError):
                    continue

        start_data += len(products_list)
        # `delay` es el espaciado mínimo entre requests: si Dropi ya tardó
        # en responder, solo se espera lo que falte.
        remaining = delay - (time.monotonic() - page_started)
        if remaining > 0:
            time.sleep(remaining)

    return catalog


# Campos cuyo cambio sí se ve en la ficha (y en Google): solo estos mueven
# last_synced, que es el lastmod del sitemap. El conteo de stock, el costo o
# el precio sugerido cambian a diario y no cambian la página; si el lastmod se
# moviera con ellos, las 35.000 fichas "cambiarían" cada semana y Google deja
# de creerle a la fecha.
PAGE_FIELDS = frozenset({"price", "variants", "is_active", "name", "description", "images"})


def touches_page(changed) -> bool:
    return bool(PAGE_FIELDS & set(changed))


def apply_listing_raw(product, raw: dict, *, deactivate_zero: bool, reactivate: bool) -> tuple[set, set]:
    """Aplica a `product` lo que dice el listado de Dropi (stock, costo,
    sugerido, variantes; precio si cambió el costo). No guarda.

    Devuelve (campos cambiados, eventos) con eventos dentro de
    {"deactivated", "reactivated", "repriced"}.
    """
    from catalog.services.pricing import compute_price

    changed, events = set(), set()
    new_stock = extract_stock(raw)
    new_cost = extract_cost(raw)
    new_variants = extract_variants(raw)

    if product.stock != new_stock:
        product.stock = new_stock
        changed.add("stock")

    cost_changed = new_cost is not None and float(product.cost) != new_cost
    if cost_changed:
        product.cost = Decimal(str(new_cost))
        changed.add("cost")

    new_suggested = Decimal(str(raw.get("suggested_price") or 0))
    if new_suggested and new_suggested != product.suggested_price:
        product.suggested_price = new_suggested
        changed.add("suggested_price")

    # Si sube/baja el costo, el precio se recalcula para no perder margen.
    if cost_changed and not product.price_locked:
        decision = compute_price(product.cost, product.suggested_price, product.category)
        if decision.price != product.price:
            product.price = decision.price
            product.pricing_status = decision.status
            changed |= {"price", "pricing_status"}
            events.add("repriced")

    if new_variants and product.variants != new_variants:
        product.variants = new_variants
        changed.add("variants")

    if deactivate_zero and new_stock == 0 and product.is_active:
        product.is_active = False
        product.inactive_reason = "sin_stock"
        changed |= {"is_active", "inactive_reason"}
        events.add("deactivated")
    elif (
        reactivate and new_stock > 0 and not product.is_active
        and product.inactive_reason in ("sin_stock", "no_existe")
    ):
        # Solo republica lo que despublicó un sync automático; lo despublicado
        # a mano o sin imágenes se queda así.
        product.is_active = True
        product.inactive_reason = ""
        changed |= {"is_active", "inactive_reason"}
        events.add("reactivated")
    return changed, events

