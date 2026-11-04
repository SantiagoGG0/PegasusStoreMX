"""
Shipping cost engine — calculates per-supplier guide costs vs. cart margins.

Model:
  - Each unique supplier in the cart requires one shipping guide.
  - Guide cost depends on the buyer's city zone.
  - envio_proveedor = min(guia, max(0, guia + piso_proveedor - margen_proveedor)),
    piso = ganancia mínima por unidad según el costo (pricing.min_gain), sumada
    para los productos del proveedor (ver catalog/services/pricing.py).
  - total_shipping   = sum(envio_proveedor for each supplier)
  - "Envío Gratis" for a supplier when its items' margin >= guide cost + piso.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from django.conf import settings

from catalog.services.pricing import min_gain, shipping_charged


# ── Zonas de México ───────────────────────────────────────────────────────────
# Zona A: zonas metropolitanas y capitales grandes (nombres de Dropi México, ver
# cart/data/mexico_geo.json). Todo municipio que no esté aquí es zona B.
# PROVISIONAL: armado por tamaño de ciudad, no con guías reales. Al tener las
# primeras guías de Dropi México, mover a zona C los destinos que salgan caros
# (como en Colombia con Leticia o Mitú) y ajustar esta lista.
MEXICO_CITIES: list[tuple[str, str, str]] = [
    # Valle de México: Dropi agrupa en "Ciudad de México" las alcaldías y los
    # municipios conurbados del Estado de México.
    *((city, "CMX", "A") for city in (
        "Álvaro Obregón", "Atizapán de Zaragoza", "Azcapotzalco", "Benito Juárez",
        "Chalco de Díaz Covarrubias", "Chimalhuacan", "Coacalco de Berriozábal", "Coyoacán",
        "Cuajimalpa de Morelos", "Cuauhtémoc", "Cuautitlán Izcalli", "Ecatepec de Morelos",
        "Gustavo A. Madero", "Huixquilucan", "Ixtapaluca", "Iztacalco", "Iztapalapa",
        "La Magdalena Contreras", "La Paz", "Miguel Hidalgo", "Milpa Alta", "Naucalpan de Juárez",
        "Nezahualcóyotl", "Texcoco", "Tlalnepantla de Baz", "Tlalpan", "Tláhuac", "Tultepec",
        "Tultitlán de Mariano Escobedo", "Venustiano Carranza", "Xochimilco",
    )),
    *((city, "MEX", "A") for city in (
        "Chimalhuacán", "Chalco", "Cuautitlán", "Metepec", "Nicolás Romero", "Tecámac",
        "Toluca", "Toluca de Lerdo", "Valle de Chalco Solidaridad",
    )),
    # Guadalajara
    *((city, "JAL", "A") for city in (
        "Guadalajara", "Zapopan", "San Pedro Tlaquepaque", "Tonala", "Tlajomulco de Zúñiga", "El Salto",
    )),
    # Monterrey
    *((city, "NLE", "A") for city in (
        "Monterrey", "Guadalupe", "San Nicolás de los Garza", "Apodaca", "General Escobedo",
        "Santa Catarina", "San Pedro Garza García", "Juárez", "García",
    )),
    # Otras zonas metropolitanas grandes
    *((city, "PUE", "A") for city in ("Puebla", "San Andrés Cholula", "San Pedro Cholula", "Cuautlancingo")),
    *((city, "QUE", "A") for city in ("Querétaro", "Corregidora", "El Marqués")),
    *((city, "GUA", "A") for city in ("Leon", "Irapuato", "Celaya")),
    ("Aguascalientes", "AGU", "A"),
    *((city, "SLP", "A") for city in ("San Luis Potosí", "Soledad de Graciano Sánchez")),
    ("Mérida", "YUC", "A"),
    *((city, "BCN", "A") for city in ("Tijuana", "Mexicali")),
    *((city, "CHH", "A") for city in ("Chihuahua", "Juarez")),
    *((city, "COA", "A") for city in ("Saltillo", "Torreón")),
    ("Hermosillo", "SON", "A"),
    *((city, "SIN", "A") for city in ("Culiacán", "Mazatlán")),
    ("Morelia", "MIC", "A"),
    ("Cuernavaca", "MOR", "A"),
    ("Pachuca de Soto", "HID", "A"),
    *((city, "VER", "A") for city in ("Veracruz", "Boca del Río", "Xalapa")),
    *((city, "TAM", "A") for city in ("Reynosa", "Tampico")),
    ("Benito Juárez", "ROO", "A"),   # Cancún
]

# Build lookup sets for fast zone resolution
_CITY_ZONE_MAP: dict[str, str] = {
    city.lower(): zone for city, _, zone in MEXICO_CITIES
}
# Also index without accents for fuzzy matching
_ACCENT_MAP = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")

def _norm(s: str) -> str:
    return s.lower().translate(_ACCENT_MAP)

_CITY_NORM_MAP: dict[str, str] = {
    _norm(city): zone for city, _, zone in MEXICO_CITIES
}


class ZoneInfo(TypedDict):
    zone: str          # 'A', 'B', or 'C'
    guide_cost: int    # MXN per guide


class SupplierShipping(TypedDict):
    supplier_id: int
    margin: Decimal        # sum of (price - cost) × qty for this supplier's items
    guide_cost: int        # guide cost for the city zone
    shipping_charged: Decimal   # what the customer pays for this supplier
    is_free: bool


class ShippingResult(TypedDict):
    zone: str
    guide_cost: int                        # per-guide cost for this zone
    total_guides_cost: Decimal             # guide_cost × unique suppliers
    total_margin: Decimal                  # total product margin in cart
    total_shipping: Decimal                # total shipping charged to customer
    supplier_breakdown: list[SupplierShipping]
    fully_free: bool                       # True when total_shipping == 0
    city: str                              # city used for calculation


def get_zone(city: str) -> ZoneInfo:
    """Return zone label and guide cost for a given city name."""
    # Zona C solo para destinos remotos de la lista (hoy ninguno). Un
    # municipio que no está en la lista va a la B.
    if not city:
        return ZoneInfo(zone="B", guide_cost=settings.SHIPPING_ZONE_B_COST)
    raw = city.strip().lower()
    norm = _norm(raw)
    zone = _CITY_ZONE_MAP.get(raw) or _CITY_NORM_MAP.get(norm) or "B"
    return ZoneInfo(zone=zone, guide_cost=_zone_costs()[zone])


def _zone_costs() -> dict[str, int]:
    return {
        "A": settings.SHIPPING_ZONE_A_COST,
        "B": settings.SHIPPING_ZONE_B_COST,
        "C": settings.SHIPPING_ZONE_C_COST,
    }


def zones_in_use() -> set[str]:
    """Zonas con al menos un municipio (la B siempre: es la de los que no
    están en la lista)."""
    return set(_CITY_ZONE_MAP.values()) | {"B"}


def max_guide_cost() -> int:
    """Guía más cara a la que de verdad puede ir un pedido. Con la zona C
    vacía es la B: exigir margen para la C le quitaba el "envío gratis" a
    productos que en ningún municipio cobran envío."""
    costs = _zone_costs()
    return max(costs[z] for z in zones_in_use())


def states_with_zone_c() -> set[str]:
    """Códigos de estado con algún municipio en zona C."""
    return {state for _, state, zone in MEXICO_CITIES if zone == "C"}


def calc_shipping(cart_lines: list[dict], city: str = "") -> ShippingResult:
    """
    Calculate shipping costs per supplier for a given city.

    cart_lines: iterable of cart line dicts with keys:
        price, cost, quantity, supplier_id
    city: buyer's city name (empty string → worst-case Zone C).

    Returns ShippingResult with per-supplier breakdown and totals.
    """
    zone_info = get_zone(city)
    guide_cost = zone_info["guide_cost"]

    # Group margin by supplier
    supplier_margins: dict[int, Decimal] = {}
    supplier_keep: dict[int, Decimal] = {}
    for line in cart_lines:
        sid = int(line.get("supplier_id") or 0)
        price = Decimal(str(line.get("price") or "0"))
        cost = Decimal(str(line.get("cost") or "0"))
        qty = int(line.get("quantity") or 1)
        margin = (price - cost) * qty
        supplier_margins[sid] = supplier_margins.get(sid, Decimal("0")) + margin
        supplier_keep[sid] = supplier_keep.get(sid, Decimal("0")) + min_gain(cost) * qty

    breakdown: list[SupplierShipping] = []
    total_shipping = Decimal("0")
    total_margin = Decimal("0")
    guide_cost_d = Decimal(str(guide_cost))

    for sid, margin in supplier_margins.items():
        charged = shipping_charged(margin, guide_cost_d, supplier_keep[sid])
        total_shipping += charged
        total_margin += margin
        breakdown.append(SupplierShipping(
            supplier_id=sid,
            margin=margin,
            guide_cost=guide_cost,
            shipping_charged=charged,
            is_free=charged == Decimal("0"),
        ))

    # Sort breakdown: free suppliers first, then by charged ascending
    breakdown.sort(key=lambda s: (not s["is_free"], s["shipping_charged"]))

    return ShippingResult(
        zone=zone_info["zone"],
        guide_cost=guide_cost,
        total_guides_cost=guide_cost_d * len(supplier_margins),
        total_margin=total_margin,
        total_shipping=total_shipping,
        supplier_breakdown=breakdown,
        fully_free=total_shipping == Decimal("0"),
        city=city or "",
    )


def shipping_from_session(cart, visitor_city: dict | None) -> ShippingResult:
    """
    Convenience wrapper: computes shipping using cart lines and session city dict.
    Passes city name; falls back to Zone C when visitor_city is None.
    """
    city = (visitor_city or {}).get("city", "")
    lines = list(cart.cart.values())
    return calc_shipping(lines, city)
