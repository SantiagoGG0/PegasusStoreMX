"""
Puntaje de relevancia (0-100) que ordena el catálogo por defecto.

    score = economía × calidad × stock × peso_categoría × penalizaciones

- economía: ganancia neta esperada por pedido frente a 2× la ganancia
            mínima del producto (pricing.min_gain) (0..1).
- calidad:  número de imágenes válidas, descripción y reseñas reales (0..1).
- stock:    pocas unidades = riesgo de quiebre después de la venta (0..1).
- peso:     prioridad comercial de la categoría (settings.PRICING_CATEGORY_PROFILES).
- precio:   un comprador que no conoce la tienda prueba primero con una
            compra pequeña: el rango impulsivo ($35.000–$160.000) va
            adelante y los tickets altos bajan (price_factor).

El resultado se normaliza dividiendo por el peso máximo configurado, así un
producto perfecto de la categoría más prioritaria llega a 100.
"""
import math

from django.conf import settings

from .pricing import (
    STATUS_FREE_SHIPPING,
    STATUS_LOW_MARGIN,
    category_key,
    category_profile,
    expected_net_profit,
    min_gain,
)


def _max_weight() -> float:
    weights = [p.get("weight", 1.0) for p in settings.PRICING_CATEGORY_PROFILES.values()]
    return max([settings.PRICING_DEFAULT_PROFILE["weight"], *weights])


def price_factor(price) -> float:
    """Pondera el precio para el orden "Relevancia" (ver docstring)."""
    value = float(price or 0)
    if value < 35_000:
        return 0.85
    if value <= 160_000:
        return 1.0
    if value <= 300_000:
        return 0.8
    return 0.6


def compute_rank_score(product) -> int:
    profile = category_profile(category_key(product.category))

    keep = min_gain(product.cost)
    net = float(expected_net_profit(product.price - product.cost, keep))
    target = max(float(keep), 5_000.0) * 2
    economics = 0.15 + 0.85 * max(0.0, min(net / target, 1.0)) if net > 0 else 0.1

    n_images = len(product.images or [])
    images = min(n_images, 5) / 5
    if n_images < settings.CATALOG_MIN_IMAGES:
        images *= 0.5
    has_description = len(product.description_unique or product.description or "") >= 200
    has_reviews = bool(product.rating_count)
    quality = 0.6 * images + 0.25 * has_description + 0.15 * has_reviews

    stock = min(1.0, math.log10(max(product.stock, 1)) / 2)  # 100+ unidades = 1.0

    score = economics * (0.3 + 0.7 * quality) * (0.4 + 0.6 * stock)
    score *= profile["weight"] / _max_weight()
    score *= price_factor(product.price)
    if product.pricing_status == STATUS_FREE_SHIPPING:
        score *= 1.15  # "envío gratis" convierte mejor
    elif product.pricing_status == STATUS_LOW_MARGIN:
        score *= 0.35
    if product.seo_exclusion or product.image_flagged:
        score *= 0.2

    return max(0, min(100, round(score * 100)))
