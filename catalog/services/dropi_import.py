"""
Shared upsert logic for importing Dropi products.
Used by both catalog/admin.py and the import_products management command.
"""
from decimal import Decimal

from ..models import Product
from .categorization import classify_product_text, ensure_store_category
from .description_sanitizer import sanitize_product_description

CDN_BASE = "https://d39ru7awumhhs2.cloudfront.net/"


def parse_images(raw: dict) -> list:
    """Extract and normalize image URLs from a Dropi product dict."""
    images = raw.get("gallery") or raw.get("photos") or raw.get("images") or []
    cleaned = []
    for img in images:
        if isinstance(img, dict):
            url_s3 = img.get("urlS3")
            url_direct = img.get("url")
            if url_s3:
                cleaned.append({"url": CDN_BASE + url_s3})
            elif url_direct:
                cleaned.append({"url": url_direct})
        elif isinstance(img, str) and img:
            cleaned.append({"url": img})
    return cleaned


def parse_stock(raw: dict) -> int:
    """Sum stock across warehouse_product entries; fall back to variant-level stock."""
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


def upsert_product(raw: dict, price_override: Decimal | None = None) -> tuple[Product, bool]:
    """
    Parse a raw Dropi product dict and upsert into the local DB.

    Args:
        raw: Raw product dict from Dropi API.
        price_override: If given, always set product.price to this value.
                        If None, falls back to the legacy behaviour:
                        set price = suggested_price only when price is still 0.

    Returns:
        (product, created) tuple.
    """
    dropi_id = raw.get("id") or raw.get("products_id")
    name = (raw.get("name") or "").strip()
    description = (
        raw.get("description") or raw.get("dropi_app_description") or ""
    ).strip()
    description = sanitize_product_description(description)

    # supplier_id: top-level user_id or nested user.id
    supplier_id = raw.get("user_id") or raw.get("supplier_id") or 0
    if not supplier_id and isinstance(raw.get("user"), dict):
        supplier_id = raw["user"].get("id", 0)

    cost_raw = raw.get("sale_price") or raw.get("price") or 0
    suggested_raw = raw.get("suggested_price") or cost_raw
    cost = Decimal(str(cost_raw))
    suggested = Decimal(str(suggested_raw))

    stock = parse_stock(raw)
    images = parse_images(raw)
    variants = raw.get("variations") or raw.get("variants") or raw.get("attributes") or []

    # Dropi category is external input. Store category is Pegasus-curated.
    dropi_category_id = ""
    dropi_category_name = ""
    categories_raw = raw.get("categories") or []
    if categories_raw and isinstance(categories_raw, list):
        first_cat = categories_raw[0]
        if isinstance(first_cat, dict):
            dropi_category_name = first_cat.get("name", "").strip()
            pivot = first_cat.get("pivot") or {}
            dropi_category_id = str(pivot.get("category_id") or dropi_category_name)

    classification = classify_product_text(
        name=name,
        description=description,
        dropi_category_name=dropi_category_name,
    )
    store_category = ensure_store_category(classification.category_key)

    existing = (
        Product.objects.filter(dropi_id=dropi_id)
        .only("pk", "category_locked", "category_id", "images", "gallery_synced_at")
        .first()
    )
    category_defaults = {
        "dropi_category_id": dropi_category_id,
        "dropi_category_name": dropi_category_name,
        "category_confidence": classification.confidence,
        "category_reason": classification.reason,
    }
    if not (existing and existing.category_locked):
        category_defaults["category"] = store_category

    # El listado de Dropi solo trae la foto principal. Si la galería completa
    # ya se trajo del detalle (sync_galleries), no se pisa con esa única foto.
    image_defaults = {"images": images}
    if existing and existing.gallery_synced_at and len(existing.images or []) >= len(images):
        image_defaults = {}

    product, created = Product.objects.update_or_create(
        dropi_id=dropi_id,
        defaults={
            "name": name,
            "description": description,
            "supplier_id": supplier_id,
            "cost": cost,
            "stock": stock,
            "suggested_price": suggested if raw.get("suggested_price") else Decimal("0"),
            "variants": variants,
            **image_defaults,
            **category_defaults,
        },
    )

    # Price logic
    if price_override is not None:
        if product.price != price_override:
            product.price = price_override
            product.save(update_fields=["price"])
    elif product.price == 0 and suggested > 0:
        product.price = suggested
        product.save(update_fields=["price"])

    return product, created
