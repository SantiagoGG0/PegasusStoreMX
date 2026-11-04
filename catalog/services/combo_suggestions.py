"""
Sugerencias de combo para productos que superan el techo de envío
(Product.needs_combo). Nunca despublica ni decide nada automáticamente —
solo propone candidatos del mismo catálogo para que el admin arme el combo,
ajuste el precio base, o descarte el producto a mano.
"""
from __future__ import annotations

from decimal import Decimal

from ..models import Product


def suggest_combo_candidates(product: Product, limit: int = 3) -> list[Product]:
    """
    Candidatos para combinar con `product` en el mismo pedido: misma
    categoría, ya activos, rentables por sí mismos (no necesitan combo ellos
    también), ordenados por costo Dropi más parecido al del producto base
    (spread predecible del margen combinado).
    """
    if not product.category_id or not product.pk:
        return []

    own_cost = product.cost or Decimal("0")

    candidates = (
        Product.objects.filter(is_active=True, category_id=product.category_id)
        .exclude(pk=product.pk)
        .exclude(cost=0)
        .only("id", "name", "slug", "price", "cost", "category_id")
    )

    scored: list[tuple[Decimal, Product]] = []
    for candidate in candidates:
        if candidate.needs_combo or not candidate.is_profitable:
            continue
        cost_diff = abs(candidate.cost - own_cost)
        scored.append((cost_diff, candidate))

    scored.sort(key=lambda pair: pair[0])
    return [candidate for _, candidate in scored[:limit]]
