import re
import unicodedata

from django.db.models import Count, Q

from .models import LISTING_EXCLUSIONS, Category


_CATEGORY_ALIASES = {
    "accesorios para vehiculos carro moto bicicleta": ("accesorios", "Accesorios"),
    "bebe": ("bebes", "Bebés"),
    "bebes": ("bebes", "Bebés"),
    "belleza y cuidado personal": ("belleza", "Belleza"),
    "bisuteria": ("moda_accesorios", "Moda y Accesorios"),
    "capilar": ("belleza", "Belleza"),
    "deporte": ("deporte_fitness", "Deporte y Fitness"),
    "deportes": ("deporte_fitness", "Deporte y Fitness"),
    "electronica": ("tecnologia", "Tecnología"),
    "fitness": ("deporte_fitness", "Deporte y Fitness"),
    "gadgets": ("tecnologia", "Tecnología"),
    "salud y bienestar": ("salud_bienestar", "Salud y Bienestar"),
    "sandalias": ("moda_accesorios", "Moda y Accesorios"),
    "tecnologia": ("tecnologia", "Tecnología"),
    "tenis": ("moda_accesorios", "Moda y Accesorios"),
    "textiles": ("moda_accesorios", "Moda y Accesorios"),
}


def normalize_category_name(name: str) -> str:
    """Normalize Dropi category labels so accents/case do not split navigation."""
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^a-zA-Z0-9]+", " ", ascii_name)
    return re.sub(r"\s+", " ", ascii_name).strip().casefold()


def category_nav_key(name: str) -> str:
    normalized = normalize_category_name(name)
    return _CATEGORY_ALIASES.get(normalized, (normalized, ""))[0]


def category_nav_label(name: str) -> str | None:
    normalized = normalize_category_name(name)
    return _CATEGORY_ALIASES.get(normalized, ("", None))[1]


def get_nav_categories() -> list[Category]:
    """Categorías del menú. Solo las que tienen productos visibles: activos,
    con slug, sin imagen marcada y sin exclusión de listas (p. ej. Bienestar
    íntimo, cuyos productos son todos del criterio e). Si vuelven a tener
    productos visibles, reaparecen solas.

    Se cachea NAV_CACHE_SECONDS: contar productos por categoría costaba
    ~250 ms y se pedía varias veces en cada página."""
    from django.conf import settings
    from django.core.cache import cache

    timeout = getattr(settings, "NAV_CACHE_SECONDS", 600)
    if timeout:
        cached = cache.get("nav_categories_v1")
        if cached is not None:
            return cached
    result = _compute_nav_categories()
    if timeout:
        cache.set("nav_categories_v1", result, timeout)
    return result


def _compute_nav_categories() -> list[Category]:
    roots = list(
        Category.objects.filter(parent__isnull=True)
        .annotate(
            active_product_count=Count(
                "products",
                filter=Q(
                    products__is_active=True,
                    products__image_flagged=False,
                )
                & ~Q(products__slug="")
                & ~Q(products__seo_exclusion__in=LISTING_EXCLUSIONS),
                distinct=True,
            )
        )
        .filter(active_product_count__gt=0)
        .prefetch_related("children")
        .order_by("name", "id")
    )

    grouped: dict[str, Category] = {}
    labels: dict[str, str] = {}
    for category in roots:
        key = category_nav_key(category.name)
        labels[key] = category_nav_label(category.name) or labels.get(key, category.name)
        current = grouped.get(key)
        current_count = getattr(current, "active_product_count", 0) if current else -1
        category_count = getattr(category, "active_product_count", 0)
        if current is None or (category_count, -category.id) > (current_count, -current.id):
            grouped[key] = category

    nav_categories = list(grouped.values())
    for category in nav_categories:
        label = labels.get(category_nav_key(category.name))
        if label:
            category.name = label

    return sorted(nav_categories, key=lambda category: normalize_category_name(category.name))


def category_filter_dropi_ids(category_id: str) -> list[str]:
    category = (
        Category.objects.filter(dropi_id=category_id)
        .select_related("parent")
        .first()
    )
    if not category:
        return [category_id]
    if category.parent_id is not None:
        return [category.dropi_id]

    selected_key = category_nav_key(category.name)
    dropi_ids: list[str] = []
    for root in Category.objects.filter(parent__isnull=True).prefetch_related("children"):
        if category_nav_key(root.name) != selected_key:
            continue
        dropi_ids.append(root.dropi_id)
        dropi_ids.extend(child.dropi_id for child in root.children.all())

    return dropi_ids or [category.dropi_id]
