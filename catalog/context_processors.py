from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg

from .navigation import get_nav_categories


def _site_rating_average():
    """Cached sitewide average rating, used only for a trust badge in the header/hero."""
    # Se guarda en una tupla: sin reseñas el promedio es None, y un None
    # directo en caché se confundía con "no está" y se recalculaba siempre.
    cached = cache.get("site_rating_average_v2")
    if cached is not None:
        return cached[0]
    from .models import Product

    value = (
        Product.objects.filter(is_active=True, rating_count__gt=0)
        .aggregate(avg=Avg("rating_average"))
        .get("avg")
    )
    result = round(float(value), 1) if value else None
    cache.set("site_rating_average_v2", (result,), 3600)
    return result


def _delivery_info(cfg: dict) -> dict:
    from .services.delivery import DELIVERY_RANGE_TEXT, DELIVERY_ZONES_TEXT

    hour = int(cfg["dispatch_cutoff_hour"])
    suffix = "a. m." if hour < 12 else "p. m."
    return {
        "range_text": DELIVERY_RANGE_TEXT,
        "zones_text": DELIVERY_ZONES_TEXT,
        "cutoff_label": f"{(hour % 12) or 12}:00 {suffix}",
    }


def store(request):
    """Datos de la tienda para las plantillas (fuente: catalog.store_config,
    editable en el admin en "Configuración de la tienda")."""
    from .store_config import store_config

    cfg = store_config()
    return {
        "store": cfg,
        "enable_prepaid_payment": getattr(settings, "ENABLE_PREPAID_PAYMENT", False),
        "nav_categories": get_nav_categories(),
        "site_rating_average": _site_rating_average(),
        "delivery_info": _delivery_info(cfg),
    }
