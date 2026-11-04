"""
Motor de precios del catálogo: piso por costo, techo por mercado.

Piso — ganancia mínima por unidad entregada según el costo del producto
(settings.PRICING_MIN_GAIN_LADDER): un producto de $7.000 debe dejar al menos
$7.000; uno de $40.000, $18.000; uno caro, un % del costo.

Techo — lo que el mercado paga: el precio sugerido de Dropi es la referencia
de valor percibido. Cuando un proveedor sugiere $79.900 para algo que cuesta
$18.000, el precio se acerca a ese valor y la ganancia supera de lejos el
piso. Nunca más de MAX_OVER_SUGGESTED por encima del sugerido (más estrecho en
productos caros, donde el comprador compara más).

Envío (cart/shipping.py) — por cada guía, la tienda conserva la suma de los
pisos de lo que va en ella (K). El checkout cobra lo que falte:

    envío cobrado = min(G, max(0, G + K − margen))

- margen ≥ G + K     → envío gratis; la tienda gana margen − G.
- K ≤ margen < G + K → el cliente paga parte de la guía; la tienda gana K.
- margen < K         → el cliente paga la guía completa; gana el margen.

Para el cliente el total (precio + envío) es el mismo en los dos primeros
casos, así que siempre que el mercado lo permita se sube el precio hasta
costo + G + K y se muestra "envío gratis", que convierte mejor.

Ningún estado despublica productos: "bajo margen" solo baja en el ranking.
"""
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from django.conf import settings
from django.db.models import Case, DecimalField, ExpressionWrapper, F, Value, When
from django.db.models.functions import Greatest

STATUS_FREE_SHIPPING = "envio_gratis"
STATUS_PAID_SHIPPING = "envio_pagado"
STATUS_LOW_MARGIN = "bajo_margen"
STATUS_NO_COST = "sin_costo"


@dataclass(frozen=True)
class PriceDecision:
    price: Decimal
    status: str


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def category_key(category) -> str:
    """'store:belleza' → 'belleza'. Acepta un Category, su dropi_id o None."""
    raw = getattr(category, "dropi_id", category) or ""
    return str(raw).split(":", 1)[-1]


def category_profile(key: str) -> dict:
    profile = dict(settings.PRICING_DEFAULT_PROFILE)
    profile.update(settings.PRICING_CATEGORY_PROFILES.get(key, {}))
    return profile


# ── Piso: escalera de ganancia mínima ────────────────────────────────────────

def _ladder_step(cost: Decimal):
    for upper, fixed, pct in settings.PRICING_MIN_GAIN_LADDER:
        if upper is None or cost < upper:
            return fixed, pct
    raise ValueError("PRICING_MIN_GAIN_LADDER debe terminar con un tramo sin tope (None)")


def min_gain(cost) -> Decimal:
    """Ganancia mínima por unidad entregada para un producto de este costo."""
    cost = _d(cost)
    if cost <= 0:
        return Decimal("0")
    fixed, pct = _ladder_step(cost)
    return max(_d(fixed), cost * _d(pct))


def min_gain_expression(cost_field: str = "cost"):
    """min_gain() como expresión de base de datos, para filtrar en el ORM."""
    output = DecimalField(max_digits=12, decimal_places=2)
    cost = F(cost_field)
    whens, lower = [], None
    for upper, fixed, pct in settings.PRICING_MIN_GAIN_LADDER:
        gain = Greatest(
            Value(_d(fixed), output_field=output),
            ExpressionWrapper(cost * Value(_d(pct), output_field=output), output_field=output),
        )
        if upper is None:
            default = gain
            break
        whens.append(When(**{f"{cost_field}__lt": upper}, then=gain))
    return Case(*whens, default=default, output_field=output)


def max_over_suggested(cost) -> Decimal:
    if _d(cost) >= _d(settings.PRICING_EXPENSIVE_FROM):
        return _d(settings.PRICING_MAX_OVER_SUGGESTED_EXPENSIVE)
    return _d(settings.PRICING_MAX_OVER_SUGGESTED)


# ── Envío y ganancia ─────────────────────────────────────────────────────────

def shipping_charged(margin, guide_cost, keep) -> Decimal:
    """Envío que paga el cliente por una guía: margen y ganancia mínima (keep)
    son la suma de los productos que van en esa guía."""
    guide = _d(guide_cost)
    return min(guide, max(Decimal("0"), guide + _d(keep) - _d(margin)))


def delivered_profit(margin, keep, guide_cost=None) -> Decimal:
    guide = _d(settings.SHIPPING_ZONE_A_COST if guide_cost is None else guide_cost)
    margin = _d(margin)
    return margin + shipping_charged(margin, guide, keep) - guide


def expected_net_profit(margin, keep, guide_cost=None) -> Decimal:
    """Ganancia neta esperada por guía (MXN), descontando rechazos COD."""
    rate = _d(settings.COD_REJECTION_RATE)
    loss = _d(settings.COD_REJECTION_LOSS)
    return (Decimal("1") - rate) * delivered_profit(margin, keep, guide_cost) - rate * loss


def status_for(margin, keep) -> str:
    margin, keep = _d(margin), _d(keep)
    if margin >= _d(settings.SHIPPING_ZONE_A_COST) + keep:
        return STATUS_FREE_SHIPPING
    if margin >= keep:
        return STATUS_PAID_SHIPPING
    return STATUS_LOW_MARGIN


# ── Precio ───────────────────────────────────────────────────────────────────

def charm_round(price: Decimal) -> Decimal:
    """Redondea hacia arriba al siguiente precio terminado en 9, como se ve en
    México: hasta $999 de 10 en 10 (127 → 129, 130 → 139); desde $1,000 de
    100 en 100 (1,234 → 1,299). En Colombia era de 1.000 en 1.000 (59.900):
    con pesos mexicanos eso subía un producto de $127 a $900."""
    price = _d(price)
    step = Decimal("100") if price >= 991 else Decimal("10")
    steps = ((price + 1) / step).to_integral_value(rounding=ROUND_CEILING)
    return steps * step - 1


def compute_price(cost, suggested, category=None) -> PriceDecision:
    cost, suggested = _d(cost), _d(suggested)
    if cost <= 0:
        price = charm_round(suggested) if suggested > 0 else Decimal("0")
        return PriceDecision(price=price, status=STATUS_NO_COST)

    keep = min_gain(cost)
    market = cost * _d(category_profile(category_key(category))["markup"])
    cap = None
    # Un sugerido con el que ni el techo supera el costo es un dato mal cargado
    # por el proveedor ($1, $10, un precio por unidad en un pack...), no un
    # precio de mercado: usarlo de techo dejaba productos en $900 o vendidos a
    # pérdida. Se ignora y manda el piso por costo.
    if suggested > 0 and suggested * max_over_suggested(cost) > cost:
        cap = suggested * max_over_suggested(cost)
        # En Dropi México el sugerido está casi pegado al costo (≈1,3×): no es
        # el precio de mercado. El techo también puede ser un múltiplo del
        # costo, para que el precio absorba parte de la guía.
        cost_cap = cost * _d(getattr(settings, "PRICING_MAX_COST_MULTIPLE", 0))
        cap = max(cap, cost_cap)
        market = min(max(market, suggested), cap)

    guide = _d(settings.SHIPPING_ZONE_A_COST)
    free_price = cost + guide + keep
    paid_price = cost + keep
    if cap is None or free_price <= cap:
        price = max(market, free_price)
    elif paid_price <= cap:
        # No alcanza para envío gratis: el precio sube hasta dejar el envío en
        # PRICING_TARGET_SHIPPING (o hasta el techo). El total del cliente y la
        # ganancia de la tienda son los mismos; solo baja el envío visible,
        # que es lo que más hace abandonar la compra.
        target = _d(getattr(settings, "PRICING_TARGET_SHIPPING", guide))
        target_price = cost + keep + max(Decimal("0"), guide - target)
        price = max(market, paid_price, min(cap, target_price))
    else:
        price = market

    price = charm_round(price)
    return PriceDecision(price=price, status=status_for(price - cost, keep))
