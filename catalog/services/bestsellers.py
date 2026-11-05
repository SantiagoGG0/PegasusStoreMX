"""
"Los más pedidos" del inicio. Antes dependía solo de marcar productos como
destacados a mano; sin ninguno marcado la sección desaparecía y el inicio
quedaba casi sin productos.

Orden de relleno (sin repetir):
  1. Lo más pedido de verdad en los últimos BESTSELLER_DAYS días.
  2. Los destacados a mano (is_featured).
  3. Los de mejor relevancia (rank_score) en el rango de precio que más
     convierte con pago contra entrega en una tienda nueva
     (IMPULSE_PRICE_MIN–IMPULSE_PRICE_MAX), con stock y al menos 2 fotos.

Se cachea la lista de ids, no los objetos.
"""
from __future__ import annotations

import datetime
from collections import Counter

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone

BESTSELLER_DAYS = 120
# MXN. Con la guía absorbida en el precio, el catálogo arranca en ~$299.
IMPULSE_PRICE_MIN = 299
IMPULSE_PRICE_MAX = 999
CACHE_KEY = "home_bestseller_ids_v2"
# Siempre se calcula y cachea la lista completa; cada llamada toma su parte
# (el hero pide 2 y la sección 12 de la misma lista).
MAX_ITEMS = 14  # 2 para el hero + 12 para la sección
CACHE_SECONDS = 1800


def _ordered_product_ids(days: int) -> list[int]:
    from orders.models import Order

    since = timezone.now() - datetime.timedelta(days=days)
    counts: Counter = Counter()
    for items in (
        Order.objects.filter(created_at__gte=since)
        .exclude(status=Order.STATUS_CANCELLED)
        .values_list("items", flat=True)
        .iterator()
    ):
        for item in items or []:
            if not isinstance(item, dict):
                continue
            try:
                pk = int(item.get("local_id") or item.get("product_id") or 0)
                qty = int(item.get("quantity") or 1)
            except (TypeError, ValueError):
                continue
            if pk:
                counts[pk] += max(qty, 1)
    return [pk for pk, _ in counts.most_common()]


def _visible():
    from catalog.models import Product

    return (
        Product.objects.listable()
        .filter(is_active=True, image_flagged=False, stock__gt=0)
        .exclude(slug="")
    )


def bestseller_ids(limit: int = MAX_ITEMS) -> list[int]:
    cached = cache.get(CACHE_KEY)
    if cached is None:
        cached = _compute_bestseller_ids()
        cache.set(CACHE_KEY, cached, CACHE_SECONDS)
    return cached[:limit]


def _compute_bestseller_ids() -> list[int]:
    visible = _visible()
    chosen: list[int] = []

    ordered = _ordered_product_ids(BESTSELLER_DAYS)
    if ordered:
        ok = set(visible.filter(pk__in=ordered[:200]).values_list("pk", flat=True))
        chosen.extend(pk for pk in ordered if pk in ok)

    for pk in visible.filter(is_featured=True).order_by("-rank_score").values_list("pk", flat=True)[:MAX_ITEMS]:
        if pk not in chosen:
            chosen.append(pk)

    if len(chosen) < MAX_ITEMS:
        fill = (
            visible.filter(price__gte=IMPULSE_PRICE_MIN, price__lte=IMPULSE_PRICE_MAX, canonical_product__isnull=True)
            .exclude(pk__in=chosen)
            .order_by(F("rating_average").desc(nulls_last=True), "-rank_score", "-stock")
            .values_list("pk", "images", "category_id")[: MAX_ITEMS * 6]
        )
        per_category: Counter = Counter()
        for pk, images, category_id in fill:
            # Al menos 2 fotos y variedad: máximo 3 por categoría.
            if len(images or []) < 2 or per_category[category_id] >= 3:
                continue
            per_category[category_id] += 1
            chosen.append(pk)
            if len(chosen) >= MAX_ITEMS:
                break
    return chosen[:MAX_ITEMS]


def bestsellers(limit: int = MAX_ITEMS) -> list:
    ids = bestseller_ids(limit)
    if not ids:
        return []
    by_pk = {
        p.pk: p
        for p in _visible().filter(pk__in=ids).select_related("category").prefetch_related("custom_images")
    }
    return [by_pk[pk] for pk in ids if pk in by_pk]


def category_cover_images(categories) -> dict[int, str]:
    """Foto de portada para categorías sin imagen propia: la del producto más
    relevante de esa categoría (cacheado una hora)."""
    from catalog.models import Product

    missing = [c.id for c in categories if not getattr(c, "image", None)]
    if not missing:
        return {}
    cached = cache.get("category_cover_images_v1") or {}
    todo = [cid for cid in missing if cid not in cached]
    if todo:
        rows = (
            _visible()
            .filter(category_id__in=todo)
            .order_by("category_id", "-rank_score")
            .values_list("category_id", "pk")
        )
        best: dict[int, int] = {}
        for category_id, pk in rows.iterator():
            best.setdefault(category_id, pk)
        for product in Product.objects.filter(pk__in=best.values()).prefetch_related("custom_images"):
            cached[product.category_id] = product.display_main_image or ""
        for cid in todo:
            cached.setdefault(cid, "")
        cache.set("category_cover_images_v1", cached, 3600)
    return {cid: cached.get(cid, "") for cid in missing}

