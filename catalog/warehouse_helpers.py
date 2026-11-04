"""Warehouse ID extraction for Dropi orders."""

from __future__ import annotations


def warehouse_id_from_raw(raw: dict, variation_id: int | None = None) -> int | None:
    """Resolve the warehouse_id to send Dropi, from a *live* Dropi product
    payload (same shape returned by DropiClient.get_product).

    Simple products carry a top-level "warehouse_product" list; variable
    products carry per-variant "warehouse_product_variation" lists (same
    shape parse_stock() already reads for stock totals). Picking the
    warehouse with stock for the exact item being ordered — rather than
    guessing a hardcoded default — avoids asking Dropi to fulfill from a
    warehouse the product isn't actually stocked in.
    """
    if not isinstance(raw, dict):
        return None

    if variation_id is not None:
        for variant in raw.get("variations") or raw.get("variants") or raw.get("attributes") or []:
            if not isinstance(variant, dict) or variant.get("id") != variation_id:
                continue
            for wh in variant.get("warehouse_product_variation") or []:
                if isinstance(wh, dict) and int(wh.get("stock") or 0) > 0 and wh.get("warehouse_id"):
                    return int(wh["warehouse_id"])
            for wh in variant.get("warehouse_product_variation") or []:
                if isinstance(wh, dict) and wh.get("warehouse_id"):
                    return int(wh["warehouse_id"])
            break

    for wh in raw.get("warehouse_product") or []:
        if isinstance(wh, dict) and int(wh.get("stock") or 0) > 0 and wh.get("warehouse_id"):
            return int(wh["warehouse_id"])
    for wh in raw.get("warehouse_product") or []:
        if isinstance(wh, dict) and wh.get("warehouse_id"):
            return int(wh["warehouse_id"])

    return None
