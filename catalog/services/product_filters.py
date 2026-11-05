"""
Quality filters for Dropi products during bulk import.
All functions operate on the raw API dict (before DB upsert).
"""
from decimal import Decimal
from dataclasses import dataclass, field


@dataclass
class FilterOptions:
    min_profit: int = 25            # MXN — floor used in pricing formula (cost + min_profit)
    min_stock: int = 5              # units available
    min_price: int = 0              # MXN — 0 = disabled; import all price points
    require_images: bool = True     # must have at least one image
    skip_existing: bool = False     # skip products already in DB
    markup_factor: float = 1.8      # price = max(suggested, cost×factor, cost+min_profit)


@dataclass
class FilterResult:
    passed: bool
    reason: str = ""


def _get_financials(raw: dict) -> tuple[Decimal, Decimal]:
    """Return (cost, suggested) from raw product dict."""
    cost_raw = raw.get("sale_price") or raw.get("price") or 0
    suggested_raw = raw.get("suggested_price") or cost_raw
    return Decimal(str(cost_raw)), Decimal(str(suggested_raw))


def _get_stock(raw: dict) -> int:
    stock = 0
    for wh in raw.get("warehouse_product") or []:
        stock += int(wh.get("stock") or 0) if isinstance(wh, dict) else 0
    if stock == 0:
        for v in raw.get("variations") or []:
            if not isinstance(v, dict):
                continue
            # Try warehouse_product_variation (detail API)
            for wv in (v.get("warehouse_product_variation") or []):
                stock += int(wv.get("stock") or 0) if isinstance(wv, dict) else 0
            # Fallback: direct stock field on variation (listing API)
            if stock == 0:
                stock += int(v.get("stock") or 0)
    return stock


def _has_images(raw: dict) -> bool:
    images = raw.get("gallery") or raw.get("photos") or raw.get("images") or []
    return bool(images)


def _calc_our_price(cost: Decimal, suggested: Decimal, markup_factor: float, min_profit: int) -> Decimal:
    """Calculate our selling price: max(suggested, cost×factor, cost+min_profit)."""
    factor = Decimal(str(markup_factor))
    min_p = Decimal(str(min_profit))
    if cost > 0:
        floor = max(cost * factor, cost + min_p)
        return max(suggested, floor) if suggested > 0 else floor
    return suggested


def check_product(raw: dict, opts: FilterOptions) -> FilterResult:
    """
    Run quality filters against a raw Dropi product dict.
    Profitability is guaranteed by the pricing formula, not enforced as a filter.
    Active filters: must have a price, sufficient stock, and images.
    """
    cost, suggested = _get_financials(raw)

    if cost == 0 and suggested == 0:
        return FilterResult(False, "sin precio")

    # min_price check is opt-in (default 0 = disabled)
    if opts.min_price > 0:
        our_price = _calc_our_price(cost, suggested, opts.markup_factor, opts.min_profit)
        if our_price < opts.min_price:
            return FilterResult(
                False,
                f"precio ${our_price:,.0f} < mínimo ${opts.min_price:,}",
            )

    stock = _get_stock(raw)
    if stock < opts.min_stock:
        return FilterResult(False, f"stock {stock} < mínimo {opts.min_stock}")

    if opts.require_images and not _has_images(raw):
        return FilterResult(False, "sin imágenes")

    return FilterResult(True)
