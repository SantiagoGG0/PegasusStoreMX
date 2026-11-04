"""Búsquedas recientes en sesión para recomendaciones en Mi cuenta."""

from __future__ import annotations

from .models import Product

SESSION_KEY = "catalog_search_history"
MAX_TERMS = 12


def record_search(request, query: str) -> None:
    term = (query or "").strip()
    if len(term) < 2:
        return
    history: list[str] = list(request.session.get(SESSION_KEY) or [])
    lowered = term.lower()
    history = [h for h in history if h.lower() != lowered]
    history.insert(0, term)
    request.session[SESSION_KEY] = history[:MAX_TERMS]
    request.session.modified = True


def get_recent_searches(request, *, limit: int = 5) -> list[str]:
    history: list[str] = list(request.session.get(SESSION_KEY) or [])
    return history[:limit]


def products_from_searches(request, *, limit: int = 8) -> tuple[list[Product], list[str]]:
    """Productos activos que coinciden con búsquedas recientes del usuario."""
    terms = get_recent_searches(request, limit=MAX_TERMS)
    if not terms:
        return [], []

    seen_ids: set[int] = set()
    products: list[Product] = []
    used_terms: list[str] = []

    for term in terms:
        if len(products) >= limit:
            break
        qs = (
            Product.objects.filter(is_active=True, name__icontains=term)
            .select_related("category")
            .order_by("-is_featured", "name")[: limit - len(products)]
        )
        added = False
        for product in qs:
            if product.pk in seen_ids:
                continue
            seen_ids.add(product.pk)
            products.append(product)
            added = True
            if len(products) >= limit:
                break
        if added and term not in used_terms:
            used_terms.append(term)

    return products, used_terms
