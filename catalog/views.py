import json
import re
import unicodedata

from django.conf import settings
from django.db import connection
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator
from django.db.models import Case, ExpressionWrapper, F, IntegerField, Q, When
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit

from config.site import absolute_url, site_base_url

from .models import Category, Product
from .navigation import category_filter_dropi_ids
from .services.content_generation import is_generated_description
from .services.delivery import delivery_estimate, dispatch_label
from .services.description_sanitizer import clean_description_for_display, extract_highlights
from .services.reviews import get_published_reviews, get_store_reviews, store_review_summary
from .search_history import record_search
from .sections import build_home_sections
from .seo import generate_json_ld, generate_meta_description, generate_og_tags, generate_seo_title

_PAGE_SIZE = 24

def _normalize_search_text(text: str) -> str:
    """Normaliza acentos/tildes para búsqueda (cómpresor → compresor)."""
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

def _get_video_embed_url(url: str) -> str:
    """Convert YouTube/Vimeo watch URLs to embeddable URLs. Pass-through everything else."""
    if not url:
        return url
    # YouTube: watch, short, and shorts
    m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})', url)
    if m:
        return f'https://www.youtube.com/embed/{m.group(1)}?rel=0'
    # Vimeo
    m = re.search(r'vimeo\.com/(\d+)', url)
    if m:
        return f'https://player.vimeo.com/video/{m.group(1)}'
    return url

_SORT_OPTIONS = {
    "random": None,  # relevancia: tramo de rank_score + orden que rota cada día
    "featured": None,  # "Relevancia" en la UI — mismo orden que random
    "rating": None,  # handled via nulls-last rating annotation below
    "price_asc": ("price",),
    "price_desc": ("-price",),
    "name": ("name",),
    "newest": ("-last_synced",),
}


def _catalog_seed() -> int:
    """Semilla del orden "Relevancia" dentro de cada tramo de puntaje: cambia
    una vez al día. Antes se guardaba una distinta en la sesión de cada visita,
    lo que creaba una cookie y hacía cada página única (imposible de servir
    desde caché, incluso a Googlebot)."""
    import datetime

    return datetime.date.today().toordinal() % 999983 or 1


def _same_supplier_first_queryset(product: Product):
    return (
        Product.objects.listable().filter(is_active=True, image_flagged=False)
        .exclude(pk=product.pk)
        .exclude(slug="")
        .annotate(
            supplier_rank=Case(
                When(supplier_id=product.supplier_id, then=0),
                default=1,
                output_field=IntegerField(),
            )
        )
        .order_by("supplier_rank", "-is_featured", "-last_synced", "name")
        .select_related("category")
        .prefetch_related("custom_images")
    )


_PRICE_BUCKETS = {
    "a": (None, 500),
    "b": (500, 1000),
    "c": (1000, None),
}


def _apply_filter_chips(products, request):
    """Free-shipping / rating / price-range chips for the catalog listing.
    Pure display filters on top of the existing catalog queryset — no change
    to product data or business rules, just narrows what's shown."""
    active = {"envio": False, "rating": False, "precio": ""}

    if request.GET.get("envio") == "1":
        active["envio"] = True
        # Igual que Product.likely_free_shipping: el margen cubre la guía de la
        # zona más cara más la ganancia mínima del producto, así el envío es
        # gratis en cualquier ciudad.
        from cart.shipping import max_guide_cost
        from catalog.services.pricing import min_gain_expression

        products = products.annotate(min_gain=min_gain_expression()).filter(
            price__gte=F("cost") + max_guide_cost() + F("min_gain")
        )

    if request.GET.get("rating") == "45":
        active["rating"] = True
        products = products.filter(rating_average__gte=4.5, rating_count__gt=0)

    precio = request.GET.get("precio", "")
    if precio in _PRICE_BUCKETS:
        active["precio"] = precio
        lo, hi = _PRICE_BUCKETS[precio]
        if lo is not None:
            products = products.filter(price__gte=lo)
        if hi is not None:
            products = products.filter(price__lt=hi)

    return products, active


def _catalog_queryset(request, stable: bool = False):
    """Active products with optional category, search, filter-chip, and sort filters."""
    products = (
        Product.objects.listable().filter(is_active=True, image_flagged=False)
        .exclude(slug="")
        .select_related("category")
        .prefetch_related("custom_images")
    )

    category_id = request.GET.get("category", "").strip()
    if category_id:
        products = products.filter(category__dropi_id__in=category_filter_dropi_ids(category_id))

    search = request.GET.get("q", "").strip()
    if search:
        if connection.vendor == 'postgresql':
            # PostgreSQL: full-text search runtime en name (sin description = más rápido)
            vector = SearchVector('name', config='spanish')
            query = SearchQuery(search, config='spanish')
            products = products.annotate(
                rank=SearchRank(vector, query)
            ).filter(rank__gte=0.01).order_by('-rank')
        else:
            # SQLite fallback: normalizar búsqueda + __icontains solo en name
            normalized = _normalize_search_text(search)
            products = products.filter(name__icontains=normalized)

    products, active_filters = _apply_filter_chips(products, request)

    sort = request.GET.get("sort", "random")
    if sort not in _SORT_OPTIONS:
        sort = "random"
    if sort in ("random", "featured"):
        # Los mejores productos (rank_score, ver catalog/services/ranking.py)
        # primero, en tramos de 10 puntos; dentro de cada tramo el orden
        # sigue siendo aleatorio por sesión para que el catálogo rote.
        # Paginación rastreable (?page=N): orden fijo, para que cada página
        # muestre siempre los mismos productos a Google; navegando, el orden
        # rota por sesión.
        seed = 1 if stable else _catalog_seed()
        products = products.annotate(
            rank_tier=ExpressionWrapper(F("rank_score") / 10, output_field=IntegerField()),
            rand_order=ExpressionWrapper(
                (F("id") * seed) % 999983,
                output_field=IntegerField(),
            ),
        ).order_by("-is_featured", "-rank_tier", "rand_order")
    elif sort == "rating":
        products = products.order_by(F("rating_average").desc(nulls_last=True), "-rating_count")
    else:
        products = products.order_by(*_SORT_OPTIONS[sort])

    return products, category_id or None, search, sort, active_filters


def _catalog_seo(request, *, search_query, category_label, selected_category, force_listing, active_filters):
    """Unique title/description/canonical per catalog state so category pages are
    indexable and distinct, while search results and filter-chip combinations
    (near-infinite, low-value permutations) canonicalize back and stay noindex."""
    base_url = site_base_url(request)
    has_filters = bool(active_filters and (active_filters.get("envio") or active_filters.get("rating") or active_filters.get("precio")))

    page = request.GET.get("page", "")
    page_qs = f"&page={page}" if page.isdigit() and int(page) > 1 else ""
    page_label = f" (página {page})" if page_qs else ""
    json_ld = None

    if search_query:
        title = f'Resultados para "{search_query}" | Pegasus Store'
        description = f'Resultados para "{search_query}" en Pegasus Store: envío a todo México y pago contra entrega.'
        clean_qs = f"?category={selected_category}" if selected_category else ""
        canonical = f"{base_url}{request.path}{clean_qs}"
        noindex = True
    elif selected_category:
        from .seo import breadcrumb_json_ld
        from .seo_content import CATEGORY_SEO

        label = category_label or "Categoría"
        copy = CATEGORY_SEO.get(str(selected_category).split(":", 1)[-1], {})
        if page_qs:
            title = f"{label}{page_label} | Pegasus Store"
        else:
            title = f"{label} con pago contra entrega en México | Pegasus Store"
            if len(title) > 60:
                title = f"{label} | Pago contra entrega | Pegasus Store"
        description = copy.get("description") or (
            f"Compra {label} online en México, con envío a todo el país y pago contra entrega."
        )
        # Cada página del listado es su propia URL canónica: así Google sigue
        # la paginación y descubre todos los productos de la categoría.
        from .seo import category_path

        canonical = f"{base_url}{category_path(selected_category)}" + (f"?page={page}" if page_qs else "")
        noindex = has_filters
        json_ld = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "CollectionPage", "name": label, "description": description, "url": canonical},
                breadcrumb_json_ld(request, [("Inicio", "/"), (label, category_path(selected_category))]),
            ],
        }
    elif force_listing:
        title = "Todo el catálogo | Pegasus Store"
        description = "Explora todo el catálogo de Pegasus Store: miles de productos con envío a todo México y pago contra entrega."
        canonical = f"{base_url}{request.path}?view=all"
        noindex = has_filters
    else:
        from .seo import organization_json_ld
        from .services.faq import faq_json_ld, store_faq

        title = "Pegasus Store — Envío a todo México con pago contra entrega"
        description = "Compra online con envío a todo México y pago contra entrega: revisas el pedido con el repartidor y solo entonces pagas. Productos para tu hogar."
        canonical = f"{base_url}{request.path}"
        noindex = False
        json_ld = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "name": "Pegasus Store",
                    "url": canonical,
                    "inLanguage": "es-CO",
                    "potentialAction": {
                        "@type": "SearchAction",
                        "target": f"{canonical}?q={{search_term_string}}",
                        "query-input": "required name=search_term_string",
                    },
                },
                organization_json_ld(request),
                faq_json_ld(store_faq()),
            ],
        }

    return {
        "seo_title": title,
        "seo_description": description,
        "seo_canonical": canonical,
        "seo_noindex": noindex,
        "seo_json_ld": mark_safe(json.dumps(json_ld, ensure_ascii=False)) if json_ld else "",
    }


def catalog_category(request, slug):
    """/categoria/<slug>/: la misma vista del catálogo con la categoría fija.
    La categoría se inyecta en GET para reutilizar filtros, orden y paginación."""
    from .seo import category_dropi_id

    dropi_id = category_dropi_id(slug)
    if not Category.objects.filter(dropi_id=dropi_id).exists():
        raise Http404
    params = request.GET.copy()
    params["category"] = dropi_id
    request.GET = params
    request.category_route = True
    return catalog_index(request)


def collection_detail(request, category_slug, slug):
    """/categoria/<categoría>/<colección>/: productos de un tipo concreto
    ("organizadores de cocina") con texto propio y preguntas frecuentes. Son
    URLs nuevas; no reemplazan la categoría ni ninguna ficha."""
    from django.utils.text import Truncator

    from .models import Collection
    from .seo import breadcrumb_json_ld, category_dropi_id, category_path
    from .services.collections import collection_products, refresh_if_stale
    from .services.faq import faq_json_ld

    collection = get_object_or_404(
        Collection.objects.select_related("category"),
        category__dropi_id=category_dropi_id(category_slug), slug=slug, is_published=True,
    )
    refresh_if_stale(collection)

    page_raw = request.GET.get("page", "")
    page_num = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1
    paginator = Paginator(collection_products(collection), _PAGE_SIZE)
    if page_num > max(paginator.num_pages, 1):
        raise Http404
    page_obj = paginator.get_page(page_num)

    base_url = site_base_url(request)
    path = collection.get_absolute_url()
    canonical = f"{base_url}{path}" + (f"?page={page_num}" if page_num > 1 else "")
    name = collection.name
    title = collection.seo_title or f"{name} con pago contra entrega | Pegasus Store"
    if len(title) > 60:
        title = f"{name} | Pegasus Store"
    if page_num > 1:
        title = f"{name}, página {page_num} | Pegasus Store"
    intro = collection.intro_paragraphs
    description = collection.meta_description or Truncator(
        f"{name} con pago contra entrega y envío a todo México. {intro[0] if intro else ''}"
    ).chars(155, truncate="…")

    category = collection.category
    faq = [item for item in (collection.faq or []) if isinstance(item, dict) and item.get("q") and item.get("a")]
    graph = [
        {"@type": "CollectionPage", "name": name, "description": description, "url": canonical},
        breadcrumb_json_ld(request, [("Inicio", "/"), (category.name, category_path(category.dropi_id)), (name, path)]),
    ]
    if faq and page_num == 1:
        graph.append(faq_json_ld(faq))

    siblings = (
        Collection.objects.filter(category=category, is_published=True, product_count__gt=0)
        .exclude(pk=collection.pk)
        .order_by("position", "name")[:12]
    )

    def page_url(number):
        return path if number == 1 else f"{path}?page={number}"

    return render(request, "catalog/collection.html", {
        "collection": collection,
        "category": category,
        "page_obj": page_obj,
        "intro_lead": intro[:1],
        "intro_more": intro[1:],
        "faq": faq if page_num == 1 else [],
        "siblings": siblings,
        "prev_url": page_url(page_obj.previous_page_number()) if page_obj.has_previous() else "",
        "next_url": page_url(page_obj.next_page_number()) if page_obj.has_next() else "",
        "seo_title": title,
        "seo_description": description,
        "seo_canonical": canonical,
        "seo_noindex": paginator.count == 0,
        "seo_json_ld": mark_safe(json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)),
    })


def catalog_index(request):
    # Sin @ensure_csrf_cookie: la página se sirve desde caché y sin cookies; el
    # token para agregar al carrito lo pide window.pgsCsrf() (base.html).
    # Refresh randomisation seed on every page-1 load
    # URL vieja /?category=store:x → 301 a /categoria/x/ (conserva filtros y
    # página). Las búsquedas dentro de una categoría se quedan como están.
    if (
        request.GET.get("category", "").startswith("store:")
        and not getattr(request, "category_route", False)
        and not request.GET.get("q")
    ):
        from django.http import HttpResponsePermanentRedirect

        from .seo import category_path

        rest = request.GET.copy()
        target = category_path(rest.pop("category")[0])
        query = rest.urlencode()
        return HttpResponsePermanentRedirect(target + (f"?{query}" if query else ""))

    page_raw = request.GET.get("page", "")
    page_num = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1
    sort_param = request.GET.get("sort", "random")
    if sort_param not in _SORT_OPTIONS:
        sort_param = "random"
    from catalog.services.gallery_sync import is_bot

    # Buscadores y páginas pedidas explícitamente: orden fijo, para que Google
    # vea cada producto en una sola página de la paginación.
    stable = page_num > 1 or is_bot(request)
    products, selected_category, search_query, sort, active_filters = _catalog_queryset(
        request, stable=stable
    )
    if search_query:
        record_search(request, search_query)
    categories = Category.objects.all().order_by("name")

    category_label = ""
    if selected_category:
        cat = Category.objects.filter(dropi_id=selected_category).only("name").first()
        category_label = cat.name if cat else ""

    paginator = Paginator(products, _PAGE_SIZE)
    if page_num > 1 and page_num > paginator.num_pages:
        raise Http404  # sin páginas "fantasma" que dupliquen la última
    page_obj = paginator.get_page(page_num)  # las siguientes llegan con scroll infinito (AJAX)

    shared = {
        "page_obj": page_obj,
        "categories": categories,
        "selected_category": selected_category,
        "category_label": category_label,
        "search_query": search_query,
        "sort": sort,
        "active_filters": active_filters,
        "force_listing": request.GET.get("view") == "all",
    }
    home_sections = build_home_sections(request, **shared)
    seo = _catalog_seo(
        request,
        search_query=search_query,
        category_label=category_label,
        selected_category=selected_category,
        force_listing=shared["force_listing"],
        active_filters=active_filters,
    )

    is_home = not (selected_category or search_query or shared["force_listing"])
    return render(request, "catalog/index.html", {"home_sections": home_sections, "is_home": is_home, **seo})


@require_GET
@ratelimit(key='ip', rate='120/m', block=True)
def catalog_products_fragment(request):
    """AJAX endpoint: returns JSON with rendered product cards for infinite scroll."""
    from django.template.loader import render_to_string

    products, _, search_query, _, _ = _catalog_queryset(request, stable=request.GET.get("stable") == "1")
    if search_query:
        record_search(request, search_query)
    paginator = Paginator(products, _PAGE_SIZE)
    try:
        page_num = int(request.GET.get("page", 2))
    except (ValueError, TypeError):
        page_num = 2
    page_obj = paginator.get_page(page_num)

    html_parts = []
    for product in page_obj:
        if not product.slug:
            continue
        html_parts.append(
            render_to_string(
                "catalog/partials/product_card.html",
                {"product": product, "catalog_fragment": True},
                request=request,
            )
        )

    html = "".join(html_parts)
    return JsonResponse({
        "html": html,
        "has_next": page_obj.has_next(),
        "page": page_obj.number,
    })


def _shipping_preview(product: Product, city: str, quantity: int = 1):
    from cart.shipping import calc_shipping

    line = {
        "price": product.price,
        "cost": product.cost,
        "quantity": quantity,
        "supplier_id": product.supplier_id,
    }
    result = calc_shipping([line], city)
    charged = result["total_shipping"]
    return "Gratis" if charged == 0 else f"${int(charged):,}"


def _product_unavailable(request, product: Product):
    """Producto retirado: página "ya no está disponible" con 4 alternativas de
    la misma categoría, para que el visitante no caiga en un callejón.

    Responde 410 (Gone) con noindex: Google lo saca del índice rápido y sin
    marcarlo como "soft 404" (un 200 que dice "no disponible"). Los agotados
    temporales (inactive_reason="sin_stock") no pasan por aquí: muestran su
    ficha normal como agotada (ver product_detail)."""
    alternatives = []
    if product.category_id:
        alternatives = list(
            Product.objects.listable().filter(
                is_active=True, image_flagged=False, stock__gt=0, category_id=product.category_id
            )
            .exclude(slug="")
            .exclude(pk=product.pk)
            .select_related("category")
            .prefetch_related("custom_images")
            .order_by("-is_featured", F("rating_average").desc(nulls_last=True), "-last_synced")[:4]
        )
    return render(
        request, "catalog/unavailable.html", {"product": product, "alternatives": alternatives}, status=410
    )


def _canonical_product(product: Product) -> Product:
    """Casi duplicado (load_seo_exclusions): la ficha declara rel=canonical
    hacia la ficha que se mantiene, mientras esa siga activa y sin noindex."""
    target = product.canonical_product
    if target and target.is_active and not target.seo_noindex:
        return target
    return product


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category", "canonical_product"), slug=slug)
    if not product.is_active:
        # Nuevo de Dropi que todavía no se publicó (esperando fotos): nunca
        # existió para Google ni para los clientes.
        if product.inactive_reason == "sin_imagenes" and product.gallery_synced_at is None:
            raise Http404
        # Agotado temporal: la ficha sigue (indexable, "agotado" en la página y
        # OutOfStock en los datos estructurados) para no perder su posición.
        if product.inactive_reason != "sin_stock":
            return _product_unavailable(request, product)
    from catalog.services.gallery_sync import ensure_gallery_on_view

    ensure_gallery_on_view(product, request)
    # Build display_images: custom uploads override Dropi images in detail page
    custom_imgs = list(product.custom_images.all())
    if custom_imgs:
        display_images = [{"url": ci.image.url, "custom": True} for ci in custom_imgs]
    else:
        display_images = product.images or []
    video_embed_url = _get_video_embed_url(product.video_url)
    # video_file takes priority over video_url
    video_file_url = product.video_file.url if product.video_file else ""
    # custom_videos: new multi-video support
    custom_videos = list(product.custom_videos.all())
    related = (
        Product.objects.listable().filter(is_active=True, category=product.category)
        .select_related("category")
        .prefetch_related("custom_images")
        .exclude(pk=product.pk)
        .exclude(slug="")[:8]
    )

    variants = []
    for v in (product.variants or []):
        if not isinstance(v, dict):
            continue
        # Individual SKU structure (attribute_values / warehouse_product_variation)
        if "attribute_values" in v or "warehouse_product_variation" in v:
            vid = v.get("id")
            attrs = v.get("attribute_values") or []
            label_parts = [a.get("value", "") for a in attrs if isinstance(a, dict)]
            label = " / ".join(label_parts) or f"Variante {vid}"
            wh_stock = sum(
                w.get("stock", 0)
                for w in (v.get("warehouse_product_variation") or [])
                if isinstance(w, dict)
            )
            variants.append({"id": vid, "label": label, "stock": wh_stock})
        # Attribute group structure (values list)
        elif "values" in v:
            attr_name = v.get("description", "")
            for val in (v.get("values") or []):
                if not isinstance(val, dict):
                    continue
                val_id = val.get("id")
                val_name = val.get("value", "")
                label = f"{attr_name}: {val_name}" if attr_name else val_name
                variants.append({"id": val_id, "label": label, "stock": product.stock})

    is_variable = bool(variants)

    visitor_city = request.session.get("visitor_city") or {}
    pdp_city = visitor_city.get("city", "")
    # Sin ciudad, la fecha se calcula para la zona más lejana (nunca se
    # promete de más) y el envío solo se afirma si es gratis en todo el país.
    delivery = delivery_estimate(pdp_city)
    shipping_cost_label = _shipping_preview(product, pdp_city) if pdp_city else ""

    # Descripción: el texto propio (description_unique) y las características
    # reales del proveedor, sin su garantía ni contactos (ver
    # description_sanitizer.clean_description_for_display).
    detail_paragraphs = clean_description_for_display(product.description)
    highlights = extract_highlights(detail_paragraphs, product.shown_name)
    intro_text = (product.description_unique or "").strip()
    if is_generated_description(intro_text):
        intro_text = ""  # texto de plantilla: no se muestra (ver is_generated_description)
    # Más de ~6 líneas en celular: se muestra recortada con "Ver descripción completa".
    details_long = sum(len(p) for p in detail_paragraphs) > 420

    product_collection = product.collections.filter(is_published=True).order_by("position").first()
    published_reviews = list(get_published_reviews(product))
    store_reviews = [] if published_reviews else get_store_reviews(limit=4, exclude_product=product)

    shipping_experiment = None
    # Sin ciudad no se muestra un envío: con la zona por defecto salían
    # $32.000 de entrada y asustaba antes de saber a dónde va el pedido.
    if product.needs_combo and pdp_city:
        from catalog.services.shipping_experiment import (
            build_shipping_experiment_context,
            log_shown,
        )
        shipping_experiment = build_shipping_experiment_context(product, pdp_city)
        if not request.session.session_key:
            request.session.save()
        log_shown(product, shipping_experiment, session_key=request.session.session_key or "")

    json_ld = generate_json_ld(product, request, collection=product_collection)

    context = {
        "product": product,
        "display_images": display_images,
        "video_embed_url": video_embed_url,
        "video_file_url": video_file_url,
        "custom_videos": custom_videos,
        "related": related,
        "variants": variants,
        "is_variable": is_variable,
        "published_reviews": published_reviews,
        "product_collection": product_collection,
        "store_reviews": store_reviews,
        "store_review_summary": store_review_summary(),
        "shipping_experiment": shipping_experiment,
        "intro_text": intro_text,
        "detail_paragraphs": detail_paragraphs,
        "details_long": details_long,
        "highlights": highlights,
        "dispatch_label": dispatch_label(),
        "wa_product_message": f"Hola, tengo una pregunta sobre {product.shown_name} (ref. PGS-{product.pk + 1000}): ",
        "seo_title": generate_seo_title(product),
        "seo_meta_description": generate_meta_description(product),
        "seo_canonical_url": absolute_url(request, _canonical_product(product).get_absolute_url()),
        "seo_og_tags": generate_og_tags(product, request),
        "seo_json_ld": mark_safe(json.dumps(json_ld, ensure_ascii=False)),
        "pdp_city": pdp_city,
        "delivery": delivery,
        "shipping_cost_label": shipping_cost_label,
    }
    return render(request, "catalog/detail.html", context)


@require_GET
def pdp_more_products(request, exclude_pk):
    """Infinite scroll fragment for PDP all-products section."""
    from django.template.loader import render_to_string

    try:
        page_num = int(request.GET.get("page", 2))
    except (ValueError, TypeError):
        page_num = 2

    source_product = get_object_or_404(Product, pk=exclude_pk, is_active=True)
    qs = _same_supplier_first_queryset(source_product)
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(page_num)

    html_parts = []
    for product in page_obj:
        html_parts.append(
            render_to_string(
                "catalog/partials/product_card.html",
                {"product": product},
                request=request,
            )
        )
    return JsonResponse({
        "html": "".join(html_parts),
        "has_next": page_obj.has_next(),
        "page": page_obj.number,
    })


@require_GET
@ratelimit(key='ip', rate='60/m', block=True)
def search_suggestions(request):
    """Live search autocomplete — returns top 6 products as JSON."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": [], "q": q})
    
    products = Product.objects.listable().filter(is_active=True).exclude(slug="")
    
    if connection.vendor == 'postgresql':
        # PostgreSQL: full-text search runtime solo en name (más rápido)
        vector = SearchVector('name', config='spanish')
        query = SearchQuery(q, config='spanish')
        products = products.annotate(
            rank=SearchRank(vector, query)
        ).filter(rank__gte=0.01).order_by('-rank', '-is_featured', 'name')[:6]
    else:
        # SQLite fallback: normalización + __icontains solo en name
        normalized = _normalize_search_text(q)
        products = products.filter(name__icontains=normalized).order_by('-is_featured', 'name')[:6]
    
    results = [
        {
            "name": p.name,
            "url": p.get_absolute_url(),
            "image": p.display_main_image or "",
            "price": str(p.price),
        }
        for p in products
    ]
    return JsonResponse({"results": results, "q": q})


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Disallow: /{settings.ADMIN_URL}",
        "Disallow: /carrito/",
        "Disallow: /pedidos/",
        # Fragmentos HTML que las páginas cargan por JS (más productos): Google
        # los rastreaba como páginas sueltas y gastaba rastreo de las fichas.
        # Los productos se descubren por el sitemap y la paginación ?page=N.
        "Disallow: /pdp-productos/",
        "Disallow: /productos/fragmento/",
        # Excepción: la página pública de seguimiento sí está en el sitemap.
        "Allow: /pedidos/seguimiento/",
        "",
        f"Sitemap: {site_base_url(request)}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
