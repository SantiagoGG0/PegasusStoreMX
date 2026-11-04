"""
Reglas Dropi: productos del mismo proveedor comparten guía de envío.
No bloqueamos mezcla por cantidad de proveedores; informamos en carrito.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from django.conf import settings

from catalog.models import Product

MAX_SUPPLIERS_PER_CART = getattr(settings, "CART_MAX_SUPPLIERS", 2)

MSG_THIRD_SUPPLIER = (
    "Tu carrito tiene productos de varias bodegas. "
    "En carrito verás detalle de guías y tiempos por bodega."
)

MSG_SECOND_SUPPLIER = (
    "Este producto es de otra bodega. Se generará una guía de envío adicional; "
    "puede haber costos y tiempos distintos. Los artículos de la misma bodega "
    "viajan juntos sin costo de envío extra entre ellos."
)

MSG_CHECKOUT_MULTI_GUIDE = (
    "Tu pedido incluye productos de {count} bodegas. Dropi generará "
    "<strong>{count} guías de envío</strong> (una por bodega). Así mejoramos "
    "tiempos de entrega frente a mezclar muchas bodegas en un solo envío."
)


def get_cart_supplier_ids(cart_lines: dict) -> set[int]:
    return {int(line.get("supplier_id") or 0) for line in cart_lines.values()}


def get_cart_product_pks(cart_lines: dict) -> set[int]:
    pks: set[int] = set()
    for key, line in cart_lines.items():
        local_id = line.get("local_id")
        if local_id:
            pks.add(int(local_id))
        else:
            pks.add(int(str(key).split("_")[0]))
    return pks


def primary_supplier_id(cart_lines: dict) -> int | None:
    """Proveedor con más unidades en el carrito (para recomendaciones)."""
    if not cart_lines:
        return None
    counts: Counter[int] = Counter()
    for line in cart_lines.values():
        counts[int(line.get("supplier_id") or 0)] += int(line.get("quantity") or 0)
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _product_already_in_cart(cart_lines: dict, product: Product, variation_id: int | None = None) -> bool:
    if variation_id:
        return f"{product.pk}_{variation_id}" in cart_lines
    if str(product.pk) in cart_lines:
        return True
    prefix = f"{product.pk}_"
    return any(str(key).startswith(prefix) for key in cart_lines)


def validate_supplier_for_add(
    cart_lines: dict,
    product: Product,
    variation_id: int | None = None,
) -> tuple[bool, str, str]:
    """
    Valida si se puede añadir una línea nueva por proveedor.
    Returns: (permitido, error, aviso)
    """
    if _product_already_in_cart(cart_lines, product, variation_id):
        return True, "", ""

    new_supplier = int(product.supplier_id or 0)
    existing = get_cart_supplier_ids(cart_lines)

    if not existing:
        return True, "", ""

    if new_supplier in existing:
        return True, "", ""

    if len(existing) >= MAX_SUPPLIERS_PER_CART:
        # No bloquear. Informar para que se comunique en carrito/banner.
        return True, "", MSG_THIRD_SUPPLIER

    return True, "", MSG_SECOND_SUPPLIER


def supplier_cart_context(cart_lines: dict) -> dict:
    ids = get_cart_supplier_ids(cart_lines)
    count = len(ids)
    return {
        "supplier_count": count,
        "multi_supplier": count > 1,
        "primary_supplier_id": primary_supplier_id(cart_lines),
        "checkout_multi_guide_message": MSG_CHECKOUT_MULTI_GUIDE.format(count=count) if count > 1 else "",
    }


SHIPPING_PENDING_LABEL = "Se calcula en el checkout según tu ciudad"


def _shipping_label(supplier_id: int, shipping_info) -> str:
    """Envío real de la bodega si ya hay ciudad (shipping_info), o el aviso de
    que se calcula en el checkout. Nunca un valor por defecto inventado."""
    if not shipping_info:
        return SHIPPING_PENDING_LABEL
    for sup in shipping_info.get("supplier_breakdown") or []:
        if int(sup.get("supplier_id") or 0) == supplier_id:
            if sup.get("is_free"):
                return "Gratis"
            return f"${int(sup['shipping_charged']):,}"
    return SHIPPING_PENDING_LABEL


def supplier_shipping_groups(cart_items: list[dict], shipping_info=None) -> list[dict]:
    """Agrupa el carrito por bodega (una guía por proveedor). shipping_info:
    resultado de calc_shipping con la ciudad del cliente, o None si aún no
    la eligió."""
    groups: dict[int, dict] = {}
    for item in cart_items:
        supplier_id = int(item.get("supplier_id") or 0)
        group = groups.setdefault(
            supplier_id,
            {
                "supplier_id": supplier_id,
                "supplier_label": "Envío estándar" if supplier_id else "Envío principal",
                "item_count": 0,
                "quantity": 0,
                "subtotal": Decimal("0"),
                "shipping_cost_label": _shipping_label(supplier_id, shipping_info),
            },
        )
        group["item_count"] += 1
        group["quantity"] += int(item.get("quantity") or 0)
        group["subtotal"] += item.get("subtotal") or Decimal("0")
    return list(groups.values())
