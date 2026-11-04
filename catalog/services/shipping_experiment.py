"""
Experimento "envío real + razón" — SOLO para productos Product.needs_combo
(ver catalog/models.py). En vez de esconder el producto o forzar el combo,
muestra el cargo de envío real de la ciudad del comprador con una razón
corta y honesta (derivada de la zona real de cart/shipping.py, no un texto
inventado), y deja la alternativa de combo visible al lado. Instrumentado
con ShippingExperimentEvent para poder medir el resultado antes de decidir
si esto se extiende al resto del catálogo "sin margen".
"""
from __future__ import annotations

from decimal import Decimal

from cart.shipping import calc_shipping, get_zone

from .combo_suggestions import suggest_combo_candidates


def real_shipping_charge(product, city: str) -> tuple[Decimal, str]:
    """(cargo, zona) para ESTE producto solo, en la ciudad dada — reutiliza
    el mismo motor de cálculo (cart.shipping.calc_shipping) usado en el
    carrito real, para que el número mostrado nunca se desincronice del
    que se cobra en checkout."""
    line = {
        "price": product.price,
        "cost": product.cost,
        "quantity": 1,
        "supplier_id": product.supplier_id,
    }
    result = calc_shipping([line], city)
    return result["total_shipping"], result["zone"]


def build_shipping_experiment_context(product, city: str) -> dict:
    """Contexto listo para el template: monto real, razón corta/larga
    honesta (zona real si aplica, o margen ajustado si el producto ya
    supera el techo incluso en Zona A), y candidatos de combo."""
    amount, zone = real_shipping_charge(product, city)

    if zone in ("B", "C"):
        reason_short = "cobertura extendida fuera de las principales ciudades"
        reason_long = (
            f"Zona {zone}: menos transportadoras cubren {city or 'esta zona'} que "
            f"Bogotá, Medellín, Cali o Barranquilla, por eso la guía de envío cuesta más."
        )
    else:
        # needs_combo ya es True usando el costo de guía más barato (Zona A),
        # así que si seguimos aquí en Zona A el motivo real es el margen del
        # producto, no la ciudad — no atribuir esto a "cobertura" sería falso.
        reason_short = "costo de envío más alto que el promedio del catálogo"
        reason_long = (
            "Este producto tiene un margen más ajustado que el resto del catálogo, "
            "así que cubrir el envío completo sube más el total mostrado en el checkout."
        )

    return {
        "city": city or "tu ciudad",
        "zone": zone,
        "amount": amount,
        "reason_short": reason_short,
        "reason_long": reason_long,
        "combo_candidates": suggest_combo_candidates(product),
    }


def log_shown(product, ctx: dict, session_key: str = "") -> None:
    from ..models import ShippingExperimentEvent

    ShippingExperimentEvent.objects.create(
        product=product,
        event_type=ShippingExperimentEvent.EVENT_SHOWN,
        city=ctx["city"],
        zone=ctx["zone"],
        shipping_amount=ctx["amount"],
        session_key=session_key or "",
    )


def _extract_item_identifiers(items: list) -> tuple[set[int], set[int]]:
    local_ids: set[int] = set()
    dropi_ids: set[int] = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        pid = it.get("product_id") or it.get("local_id")
        if pid is not None:
            try:
                local_ids.add(int(pid))
            except (TypeError, ValueError):
                pass
        did = it.get("dropi_id") or it.get("id")
        if did is not None:
            try:
                dropi_ids.add(int(did))
            except (TypeError, ValueError):
                pass
    return local_ids, dropi_ids


def log_purchase_outcome(order) -> None:
    """Llamar una vez por cada Order creada exitosamente. Para cada producto
    needs_combo dentro de ESA orden, registra si el comprador pagó el
    recargo real solo, o si lo combinó con uno de sus candidatos de combo
    sugeridos (también presente en la misma orden)."""
    from ..models import Product, ShippingExperimentEvent

    local_ids, dropi_ids = _extract_item_identifiers(order.items)
    if not local_ids and not dropi_ids:
        return

    order_products = list(
        Product.objects.filter(pk__in=local_ids) if local_ids
        else Product.objects.none()
    )
    if dropi_ids:
        seen = {p.pk for p in order_products}
        for p in Product.objects.filter(dropi_id__in=dropi_ids):
            if p.pk not in seen:
                order_products.append(p)
                seen.add(p.pk)

    order_product_ids = {p.pk for p in order_products}
    zone = get_zone(order.city or "")["zone"]

    for product in order_products:
        if not product.needs_combo:
            continue
        candidate_ids = {c.pk for c in suggest_combo_candidates(product)}
        chose_combo = bool(candidate_ids & order_product_ids)
        ShippingExperimentEvent.objects.create(
            product=product,
            event_type=(
                ShippingExperimentEvent.EVENT_CHOSE_COMBO if chose_combo
                else ShippingExperimentEvent.EVENT_PURCHASED_SURCHARGE
            ),
            city=order.city or "",
            zone=zone,
            shipping_amount=product.shipping_gap,
            order=order,
        )
