"""
Tiempos de entrega: una sola fuente para la ficha, el FAQ, las páginas
legales y el JSON-LD (antes el sitio prometía "24-72 h" mientras la ficha
calculaba hasta 5 días para la zona C).

Días hábiles = lunes a viernes. El conteo arranca el día de despacho: hoy si
es día hábil y aún no pasa la hora de corte (admin → Configuración de la tienda), si
no el siguiente día hábil.
"""
from __future__ import annotations

import datetime

from django.utils import timezone

# Días hábiles en tránsito después del despacho, por zona de cart.shipping.
DELIVERY_SPANS = {"A": (1, 2), "B": (2, 3), "C": (3, 5)}
ZONE_LABELS = {"A": "ciudades principales", "B": "ciudades intermedias", "C": "resto del país"}
DELIVERY_MIN_DAYS = min(span[0] for span in DELIVERY_SPANS.values())
DELIVERY_MAX_DAYS = max(span[1] for span in DELIVERY_SPANS.values())
# Texto corto para titulares y metas ("1 a 5 días hábiles").
DELIVERY_RANGE_TEXT = f"{DELIVERY_MIN_DAYS} a {DELIVERY_MAX_DAYS} días hábiles"
DELIVERY_ZONES_TEXT = (
    f"Ciudades principales (Bogotá, Medellín, Cali, Barranquilla…): {DELIVERY_SPANS['A'][0]} a {DELIVERY_SPANS['A'][1]} días hábiles. "
    f"Ciudades intermedias: {DELIVERY_SPANS['B'][0]} a {DELIVERY_SPANS['B'][1]}. "
    f"Resto del país: {DELIVERY_SPANS['C'][0]} a {DELIVERY_SPANS['C'][1]}."
)

_ES_WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_ES_WEEKDAYS_LONG = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_ES_MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def es_short_date(d: datetime.date) -> str:
    return f"{_ES_WEEKDAYS[d.weekday()]} {d.day} {_ES_MONTHS[d.month - 1]}"


def _now() -> datetime.datetime:
    return timezone.localtime()


def add_business_days(day: datetime.date, n: int) -> datetime.date:
    while n > 0:
        day += datetime.timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def _cutoff_hour() -> int:
    from ..store_config import store_config

    return int(store_config()["dispatch_cutoff_hour"])


def dispatch_date(now: datetime.datetime | None = None, cutoff: int | None = None) -> datetime.date:
    now = now or _now()
    cutoff = _cutoff_hour() if cutoff is None else cutoff
    today = now.date()
    if today.weekday() < 5 and now.hour < cutoff:
        return today
    return add_business_days(today, 1)


def dispatch_label(now: datetime.datetime | None = None, cutoff: int | None = None) -> str:
    """"Sale hoy" / "Sale mañana" / "Sale el lunes" para un producto con stock."""
    now = now or _now()
    day = dispatch_date(now, cutoff)
    delta = (day - now.date()).days
    if delta == 0:
        return "Sale hoy"
    if delta == 1:
        return "Sale mañana"
    return f"Sale el {_ES_WEEKDAYS_LONG[day.weekday()]}"


def delivery_estimate(city: str, now: datetime.datetime | None = None) -> dict:
    """Zona y rango de fechas de entrega para una ciudad (sin ciudad: zona C)."""
    from cart.shipping import get_zone

    zone = get_zone(city)["zone"] if city else "C"
    first, last = DELIVERY_SPANS[zone]
    start = dispatch_date(now)
    return {
        "zone": zone,
        "zone_label": ZONE_LABELS[zone],
        "eta_text": f"entre el {es_short_date(add_business_days(start, first))} y el {es_short_date(add_business_days(start, last))}",
    }
