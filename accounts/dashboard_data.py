from __future__ import annotations

from catalog.models import Product
from catalog.search_history import products_from_searches
from catalog.services import get_dashboard_review_data
from orders.models import Order


def user_display_name(user) -> str:
    full = (user.get_full_name() or "").strip()
    if full:
        return full
    first = (user.first_name or "").strip()
    if first:
        return first
    email = (user.email or "").split("@")[0]
    return email.replace(".", " ").replace("_", " ").title() if email else "Cliente"


def _orders_for_user(user):
    return Order.objects.filter(user=user)


def _collect_dropi_ids(orders_qs) -> set[int]:
    ids: set[int] = set()
    for order in orders_qs.only("items"):
        for item in order.items or []:
            raw = item.get("dropi_id")
            if raw is not None:
                try:
                    ids.add(int(raw))
                except (TypeError, ValueError):
                    pass
    return ids


def get_purchase_fallback_products(user, *, limit: int = 8) -> list[Product]:
    paid = _orders_for_user(user).exclude(status=Order.STATUS_CANCELLED)
    dropi_ids = _collect_dropi_ids(paid)
    base = Product.objects.filter(is_active=True).select_related("category")

    if dropi_ids:
        category_ids = list(
            base.filter(dropi_id__in=dropi_ids)
            .exclude(category_id__isnull=True)
            .values_list("category_id", flat=True)
            .distinct()
        )
        if category_ids:
            return list(
                base.filter(category_id__in=category_ids)
                .exclude(dropi_id__in=dropi_ids)
                .order_by("-is_featured", "name")[:limit]
            )

    return list(base.exclude(slug="").order_by("-is_featured", "-id")[:limit])


def build_dashboard_context(user, request) -> dict:
    LIMIT = 200
    search_products, search_terms = products_from_searches(request, limit=LIMIT)
    recommendation_source = "search" if search_products else (
        "purchases" if _orders_for_user(user).exists() else "featured"
    )

    # Pad with remaining active products up to LIMIT
    seen_ids = {p.pk for p in search_products}
    if len(search_products) < LIMIT:
        fallback = (
            Product.objects.filter(is_active=True)
            .exclude(slug="")
            .exclude(pk__in=seen_ids)
            .order_by("-is_featured", "-id")[: LIMIT - len(search_products)]
        )
        search_products = search_products + list(fallback)

    if not recommendation_source:
        recommendation_source = "featured"

    pending_reviews, my_reviews = get_dashboard_review_data(user)

    return {
        "search_terms": search_terms,
        "suggested_products": search_products,
        "recommendation_source": recommendation_source,
        "pending_reviews": pending_reviews,
        "my_reviews": my_reviews,
    }
