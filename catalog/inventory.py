"""Stock helpers for products and variants."""

from __future__ import annotations

from .models import Product


def variant_stock_from_list(variants: list, variation_id: int, fallback_stock: int) -> int:
    """Resolve one variation's stock from a raw variants/variations list.

    Same shape whether it comes from Product.variants (synced cache) or a
    live Dropi API payload. Handles two Dropi structures:
    - Individual SKU: {id, attribute_values, warehouse_product_variation}
      This carries its own per-warehouse stock breakdown, which is
      authoritative EVEN WHEN IT SUMS TO ZERO — a variant genuinely out of
      stock must not be masked by the product's aggregate stock, or checkout
      will accept orders Dropi then rejects at order-creation time.
    - Attribute group: {id, description, values: [{id, value}]} — these carry
      no stock of their own, so the product-level aggregate is the best
      available signal.
    """
    for variant in variants or []:
        if not isinstance(variant, dict):
            continue
        if variant.get("id") == variation_id:
            warehouses = variant.get("warehouse_product_variation") or []
            if warehouses:
                return sum(int(w.get("stock", 0)) for w in warehouses if isinstance(w, dict))
            return fallback_stock
        for val in (variant.get("values") or []):
            if isinstance(val, dict) and val.get("id") == variation_id:
                return fallback_stock
    return 0


def variation_stock(product: Product, variation_id: int | None) -> int:
    """Return available units for a variant, or product-level stock."""
    product_stock = max(0, int(product.stock or 0))
    if variation_id is None:
        return product_stock
    return variant_stock_from_list(product.variants or [], variation_id, product_stock)


def get_available_stock(product: Product, variation_id: int | None = None) -> int:
    if variation_id is not None:
        return variation_stock(product, variation_id)
    return max(0, int(product.stock or 0))


def variation_label(product: Product, variation_id: int | None) -> str:
    if variation_id is None:
        return ""
    for variant in product.variants or []:
        if not isinstance(variant, dict):
            continue
        # Individual SKU structure
        if variant.get("id") == variation_id:
            attrs = variant.get("attribute_values") or []
            parts = [a.get("value", "") for a in attrs if isinstance(a, dict)]
            return " / ".join(parts) or f"Variante {variation_id}"
        # Attribute group structure: search within values
        for val in (variant.get("values") or []):
            if isinstance(val, dict) and val.get("id") == variation_id:
                attr_name = variant.get("description", "")
                val_name = val.get("value", "")
                return f"{attr_name}: {val_name}" if attr_name else val_name
    return f"Variante {variation_id}"
