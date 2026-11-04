"""
Cifras reales de confianza para mostrar al comprador: pedidos entregados,
ciudades y guías rastreables. Todo sale de la tabla de pedidos; nada se
escribe a mano en las plantillas (un número inventado que el cliente no
puede comprobar resta más confianza de la que suma).

Se cachea TRUST_CACHE_SECONDS: lo piden el inicio y la página Confianza.
"""
from __future__ import annotations

import logging
import unicodedata

from django.core.cache import cache
from django.db import DatabaseError

logger = logging.getLogger(__name__)

TRUST_CACHE_SECONDS = 1800
GUIDES_LIMIT = 12


def _city_key(city: str) -> str:
    text = unicodedata.normalize("NFKD", (city or "").strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def pretty_city(city: str) -> str:
    """"jesus maria" / "JESÚS MARÍA" → "Jesús María" cuando hay una grafía con tilde conocida."""
    from cart.mexico_geo import municipios_by_state_label

    key = _city_key(city)
    if not key:
        return ""
    lookup = cache.get("trust_city_lookup_v1")
    if lookup is None:
        lookup = {_city_key(c): c for cities in municipios_by_state_label().values() for c in cities}
        cache.set("trust_city_lookup_v1", lookup, 86400)
    return lookup.get(key) or city.strip().title()


def mask_guide(number: str) -> str:
    """Número de guía parcial para mostrar en público: "2400••••345". Completo
    permitiría ver en la transportadora la dirección y el nombre del cliente."""
    number = (number or "").strip()
    if len(number) <= 6:
        return number[:2] + "•" * max(len(number) - 2, 0)
    return number[:4] + "•" * (len(number) - 7) + number[-3:]


def delivery_stats() -> dict:
    """{"delivered": N, "cities": M, "show": bool}. show es False mientras N
    esté por debajo del mínimo configurado en el admin."""
    cached = cache.get("trust_delivery_stats_v1")
    if cached is not None:
        return cached
    from orders.models import Order

    try:
        cities = list(
            Order.objects.filter(status=Order.STATUS_DELIVERED).values_list("city", flat=True)
        )
    except DatabaseError:
        logger.exception("Confianza: no se pudieron contar los pedidos entregados")
        return {"delivered": 0, "cities": 0, "show": False}
    delivered = len(cities)
    distinct = len({_city_key(c) for c in cities if c})
    from catalog.store_config import store_config

    minimum = int(store_config()["trust_min_delivered"])
    result = {"delivered": delivered, "cities": distinct, "show": delivered >= minimum}
    cache.set("trust_delivery_stats_v1", result, TRUST_CACHE_SECONDS)
    return result


def recent_guides(limit: int = GUIDES_LIMIT) -> list[dict]:
    """Últimas guías reales despachadas (número parcial, ver mask_guide), con
    transportadora, destino y fecha. Sin enlace de rastreo: llevaría el
    número completo. Tolerante: un error de base de datos deja la lista
    vacía (y queda en el log) en vez de tumbar la página."""
    from orders.models import Order

    try:
        orders = list(
            Order.objects.filter(status__in=[Order.STATUS_DELIVERED, Order.STATUS_SENT])
            .exclude(shipping_guide__isnull=True)
            .exclude(shipping_guide="")
            .only("shipping_guide", "status", "city", "items", "created_at", "carrier")
            .order_by("-created_at")[:limit]
        )
    except DatabaseError:
        logger.exception("Confianza: no se pudieron leer las guías recientes")
        return []

    guides = []
    for order in orders:
        number = (order.shipping_guide or "").strip()
        if not number:
            continue
        carrier = (order.carrier or "").strip()
        items = order.items if isinstance(order.items, list) else []
        packages = len(items) or 1
        guides.append({
            "number": mask_guide(number),
            "status": "Entregada" if order.status == Order.STATUS_DELIVERED else "En reparto",
            "delivered": order.status == Order.STATUS_DELIVERED,
            "city": pretty_city(order.city),
            "carrier": carrier.title() if carrier.isupper() else carrier,
            "date": order.created_at,
            "packages": packages,
        })
    return guides
