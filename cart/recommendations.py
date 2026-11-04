"""
Recomendaciones en carrito: priorizar mismo proveedor, rellenar con catálogo amplio.
"""

from __future__ import annotations

from django.conf import settings
from django.db.models import Case, IntegerField, When

from catalog.models import Product

from .cart import Cart
from .suppliers import get_cart_product_pks, primary_supplier_id

DEFAULT_LIMIT = getattr(settings, "CART_SUGGESTED_PRODUCTS_LIMIT", 48)


def products_for_cart(cart: Cart, *, limit: int | None = None) -> tuple[list[Product], int | None]:
    """
    Lista de productos sugeridos y el proveedor prioritario (si hay carrito).
    Orden: mismo proveedor (destacados primero) → resto del catálogo activo.
    """
    limit = limit or DEFAULT_LIMIT
    exclude_pks = get_cart_product_pks(cart.cart)
    base = (
        Product.objects.listable().filter(is_active=True)
        .exclude(slug="")
        .exclude(pk__in=exclude_pks)
        .select_related("category")
    )

    priority_supplier = primary_supplier_id(cart.cart)
    if priority_supplier is not None and cart.cart:
        base = base.annotate(
            supplier_rank=Case(
                When(supplier_id=priority_supplier, then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by("supplier_rank", "-is_featured", "-last_synced", "name")
    else:
        base = base.order_by("-is_featured", "-last_synced", "name")

    return list(base[:limit]), priority_supplier
