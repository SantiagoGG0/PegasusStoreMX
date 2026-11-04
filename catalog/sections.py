"""
Home page sections — extensible registry.

Enable sections via CATALOG_HOME_SECTIONS in settings.
Only catalog_grid is implemented in phase 1; others are stubs for future phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.db.models import Count, F
from django.http import HttpRequest

from .models import Product
from .store_config import store_config


# Categorías que no van en las tarjetas del inicio: "Otros" mezcla de todo y
# no ayuda a elegir (sigue en el menú y en el catálogo completo).
HOME_TILE_HIDDEN_CATEGORIES = {"store:otros"}


@dataclass
class HomeSection:
    id: str
    template: str
    context: dict[str, Any] = field(default_factory=dict)


def _section_catalog_header(page_obj, search_query: str, sort: str = "featured", selected_category=None, category_label: str = "", active_filters=None) -> dict[str, Any]:
    from .seo_content import CATEGORY_SEO

    intro = ""
    if selected_category and not search_query and getattr(page_obj, "number", 1) == 1:
        intro = CATEGORY_SEO.get(str(selected_category).split(":", 1)[-1], {}).get("intro", "")
    collections = []
    if selected_category and not search_query:
        from .models import Collection

        collections = list(
            Collection.objects.filter(category__dropi_id=selected_category, is_published=True, product_count__gt=0)
            .order_by("position", "name")
        )
    return {
        "page_obj": page_obj,
        "search_query": search_query,
        "sort": sort,
        "selected_category": selected_category,
        "category_label": category_label,
        "category_intro": intro,
        "active_filters": active_filters or {},
        "collections": collections,
    }


def _section_catalog_grid(
    *,
    page_obj,
    categories,
    selected_category: str | None,
    search_query: str,
    sort: str = "featured",
    active_filters=None,
) -> dict[str, Any]:
    from urllib.parse import urlencode

    if search_query:
        base = {"q": search_query}
        if selected_category:
            base["category"] = selected_category
    elif selected_category:
        base = {}   # la categoría va en la ruta (/categoria/x/)
    else:
        base = {"view": "all"}

    def page_url(number):
        query = urlencode({**base, **({"page": number} if number > 1 else {})})
        return f"?{query}" if query else "./"

    return {
        "page_obj": page_obj,
        "categories": categories,
        "selected_category": selected_category,
        "search_query": search_query,
        "sort": sort,
        "active_filters": active_filters or {},
        # Enlaces rastreables a la página anterior/siguiente (Google no hace scroll).
        "prev_url": page_url(page_obj.previous_page_number()) if page_obj.has_previous() else "",
        "next_url": page_url(page_obj.next_page_number()) if page_obj.has_next() else "",
        "stable_order": page_obj.number > 1,
    }


def _section_featured(request: HttpRequest, shared: dict) -> "HomeSection | None":
    """Lo más pedido: pedidos reales, destacados y relleno curado (ver
    services/bestsellers). Solo en el inicio."""
    if not _is_home_state(shared):
        return None
    from .services.bestsellers import bestsellers

    # El hero muestra los 2 primeros; la sección sigue desde el tercero para
    # no repetirlos uno debajo del otro.
    hero_on = any(e.get("id") == "hero" and e.get("enabled", True) for e in getattr(settings, "CATALOG_HOME_SECTIONS", []))
    products = bestsellers(14)
    if hero_on and len(products) >= 6:
        products = products[2:]
    products = products[:12]
    if not products:
        return None
    return HomeSection(
        id="featured",
        template="catalog/partials/section_featured.html",
        context={"featured_products": products},
    )


def section_offers_stub() -> HomeSection | None:
    """Future: /ofertas/ products with compare_at_price. Not rendered in phase 1."""
    return None


def section_novedades_stub() -> HomeSection | None:
    """Future: recently synced products. Not rendered in phase 1."""
    return None


def _is_home_state(shared: dict) -> bool:
    """True on the plain '/' landing view — no category filter, no search,
    and not explicitly asked to see the full listing (?view=all)."""
    return (
        not shared.get("selected_category")
        and not shared.get("search_query")
        and not shared.get("force_listing")
    )


def _base_active_products():
    return (
        Product.objects.listable().filter(is_active=True, image_flagged=False)
        .exclude(slug="")
        .select_related("category")
        .prefetch_related("custom_images")
    )


def _section_hero(request: HttpRequest, shared: dict) -> "HomeSection | None":
    if not _is_home_state(shared):
        return None
    from .services.bestsellers import bestsellers
    from .services.reviews import store_review_summary
    from .services.trust import delivery_stats

    products = bestsellers(2)
    if len(products) < 2:
        products = list(_base_active_products().filter(stock__gt=0).order_by("-rank_score")[:2])
    return HomeSection(
        id="hero",
        template="catalog/partials/section_hero.html",
        context={
            "hero_products": products,
            "delivery_stats": delivery_stats(),
            "review_summary": store_review_summary(),
        },
    )


def _section_marquee(request: HttpRequest, shared: dict) -> "HomeSection | None":
    if not _is_home_state(shared):
        return None
    return HomeSection(id="marquee", template="catalog/partials/section_marquee.html")


def _section_category_tiles(request: HttpRequest, shared: dict) -> "HomeSection | None":
    if not _is_home_state(shared):
        return None
    from .navigation import get_nav_categories
    from .models import Product

    cats = get_nav_categories()
    counts = {
        row["category_id"]: row["n"]
        for row in Product.objects.listable().filter(is_active=True, category__in=[c.id for c in cats])
        .values("category_id")
        .annotate(n=Count("id"))
    }
    from .services.bestsellers import category_cover_images

    cats = [c for c in cats if c.dropi_id not in HOME_TILE_HIDDEN_CATEGORIES]
    covers = category_cover_images(cats)
    for c in cats:
        c.product_count = counts.get(c.id, 0)
        c.cover_url = covers.get(c.id, "")
    return HomeSection(
        id="category_tiles",
        template="catalog/partials/section_category_tiles.html",
        context={"tile_categories": cats},
    )


def _section_how_it_works(request: HttpRequest, shared: dict) -> "HomeSection | None":
    if not _is_home_state(shared):
        return None
    from urllib.parse import quote

    whatsapp = store_config()["whatsapp"]
    wa_href = f"https://wa.me/{whatsapp}?text={quote('Hola, quiero hacer un pedido')}"
    return HomeSection(
        id="how_it_works",
        template="catalog/partials/section_how_it_works.html",
        context={"wa_href": wa_href},
    )


def _section_social_proof(request: HttpRequest, shared: dict) -> "HomeSection | None":
    """Prueba social real: reseñas de clientes; mientras haya pocas, las
    últimas guías despachadas. Sin ninguna de las dos, no se muestra."""
    if not _is_home_state(shared):
        return None
    from .services.reviews import get_store_reviews, store_review_summary
    from .services.trust import recent_guides

    reviews = get_store_reviews(limit=6)
    guides = [] if len(reviews) >= 3 else recent_guides(limit=3)
    if not reviews and not guides:
        return None
    return HomeSection(
        id="social_proof",
        template="catalog/partials/section_social_proof.html",
        context={"reviews": reviews, "guides": guides, "review_summary": store_review_summary()},
    )


def _section_faq(request: HttpRequest, shared: dict) -> "HomeSection | None":
    if not _is_home_state(shared):
        return None
    from urllib.parse import quote

    from .services.faq import store_faq

    whatsapp = store_config()["whatsapp"]
    wa_href = f"https://wa.me/{whatsapp}?text={quote('Hola, tengo una consulta sobre Pegasus Store')}"
    return HomeSection(
        id="faq",
        template="catalog/partials/section_faq.html",
        context={
            "wa_href": wa_href,
            "faq_items": store_faq(),
            "channel_url": store_config()["whatsapp_channel_url"],
        },
    )


_SECTION_BUILDERS = {
    "catalog_header": lambda request, shared: (
        None if _is_home_state(shared) else HomeSection(
            id="catalog_header",
            template="catalog/partials/section_catalog_header.html",
            context=_section_catalog_header(
                shared["page_obj"],
                shared["search_query"],
                shared.get("sort", "featured"),
                selected_category=shared.get("selected_category"),
                category_label=shared.get("category_label", ""),
                active_filters=shared.get("active_filters"),
            ),
        )
    ),
    "catalog_grid": lambda request, shared: (
        None if _is_home_state(shared) else HomeSection(
            id="catalog_grid",
            template="catalog/partials/section_catalog_grid.html",
            context=_section_catalog_grid(
                page_obj=shared["page_obj"],
                categories=shared["categories"],
                selected_category=shared["selected_category"],
                search_query=shared["search_query"],
                sort=shared.get("sort", "featured"),
                active_filters=shared.get("active_filters"),
            ),
        )
    ),
    "featured": _section_featured,
    "hero": _section_hero,
    "marquee": _section_marquee,
    "category_tiles": _section_category_tiles,
    "how_it_works": _section_how_it_works,
    "social_proof": _section_social_proof,
    "faq": _section_faq,
}


def build_home_sections(request: HttpRequest, **shared) -> list[HomeSection]:
    """Return ordered, enabled sections for the catalog home page."""
    config = getattr(settings, "CATALOG_HOME_SECTIONS", [])
    sections: list[HomeSection] = []

    for entry in config:
        if not entry.get("enabled", True):
            continue
        section_id = entry["id"]
        builder = _SECTION_BUILDERS.get(section_id)
        if builder is None:
            continue
        result = builder(request, shared)
        if result is not None:
            sections.append(result)

    return sections
