"""Sitemaps: índice en /sitemap.xml con una sección por tipo.

    /sitemap.xml             índice (sitemap_index)
    /sitemap-productos.xml   fichas indexables (sin noindex ni duplicados), en
                             páginas de PRODUCTS_PER_SITEMAP (?p=2, ?p=3…)
    /sitemap-categorias.xml  categorías de la navegación
    /sitemap-colecciones.xml colecciones publicadas (/categoria/x/y/)
    /sitemap-paginas.xml     home, confianza, legales y seguimiento

Partir las fichas en archivos de 5.000 deja ver en Search Console la
indexación de cada tramo del catálogo, y cada archivo pesa ~3 MB en vez de 24.

lastmod real: last_synced de cada producto (solo cambia con cambios visibles
en la ficha, ver stock_sync.PAGE_FIELDS); en categorías, el más reciente
de sus productos indexables; en la home, el más reciente del catálogo. Las
páginas sin fecha fiable no declaran lastmod (mejor omitirlo que inventarlo).
Las vistas se cachean en config/urls.py.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.template.response import TemplateResponse
from django.urls import reverse

from config.site import site_base_url

from .models import Product
from .seo import category_path, encode_url
from .navigation import category_filter_dropi_ids, get_nav_categories


def _indexable_products():
    return Product.objects.filter(is_active=True).indexable()


class SitemapProduct:
    """Fila liviana del sitemap de productos (sin instanciar ~40k modelos),
    con las fotos para la extensión de imágenes de Google."""

    __slots__ = ("slug", "last_synced", "images")
    MAX_IMAGES = 5

    def __init__(self, slug, last_synced, images):
        self.slug, self.last_synced, self.images = slug, last_synced, images or []

    @property
    def sitemap_images(self):
        urls = []
        for img in self.images:
            url = img.get("url") if isinstance(img, dict) else str(img)
            if url and url.startswith(("http://", "https://")):
                url = encode_url(url)
                if url not in urls:
                    urls.append(url)
        return urls[: self.MAX_IMAGES]


PRODUCTS_PER_SITEMAP = 5000


class _ProductRows:
    """Secuencia perezosa para el Paginator del sitemap: cuenta y corta en la
    base de datos, así cada archivo de 5.000 no carga las ~35.000 fichas."""

    def __init__(self, queryset):
        self._qs = queryset

    def count(self):
        return self._qs.count()

    def __len__(self):
        return self.count()

    def __getitem__(self, key):
        return [SitemapProduct(*row) for row in self._qs[key]]


class CanonicalSitemap(Sitemap):
    """Usa el host de STORE_SITE_URL en vez del host de la petición, para que
    el sitemap no liste URLs de pegasusstoreco.com o del dominio de DO."""

    protocol = "https"

    def get_domain(self, site=None):
        canonical = urlsplit(getattr(settings, "STORE_SITE_URL", "") or "")
        if canonical.netloc:
            return canonical.netloc
        return super().get_domain(site)


class CategorySitemap(CanonicalSitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        latest = dict(
            _indexable_products()
            .values_list("category__dropi_id")
            .annotate(last=Max("last_synced"))
        )
        categories = get_nav_categories()
        for category in categories:
            dates = [latest[i] for i in category_filter_dropi_ids(category.dropi_id) if latest.get(i)]
            category.sitemap_lastmod = max(dates, default=None)
        return categories

    def location(self, obj):
        return category_path(obj.dropi_id)

    def lastmod(self, obj):
        return obj.sitemap_lastmod

    def get_latest_lastmod(self):
        return max((c.sitemap_lastmod for c in self.items() if c.sitemap_lastmod), default=None)


class ProductSitemap(CanonicalSitemap):
    changefreq = "weekly"
    priority = 0.8
    limit = PRODUCTS_PER_SITEMAP

    def items(self):
        return _ProductRows(_indexable_products().order_by("pk").values_list("slug", "last_synced", "images"))

    def page_lastmods(self) -> list:
        """lastmod de cada archivo (el más reciente de sus fichas), en orden."""
        dates = list(_indexable_products().order_by("pk").values_list("last_synced", flat=True))
        return [
            max((d for d in dates[i:i + self.limit] if d), default=None)
            for i in range(0, len(dates), self.limit)
        ]

    def location(self, item):
        if not hasattr(self, "_url_template"):
            self._url_template = reverse("catalog:detail", kwargs={"slug": "__slug__"})
        return self._url_template.replace("__slug__", item.slug)

    def lastmod(self, item):
        return item.last_synced

    def get_latest_lastmod(self):
        return _indexable_products().aggregate(last=Max("last_synced"))["last"]


class CollectionSitemap(CanonicalSitemap):
    """Colecciones publicadas con productos (/categoria/x/y/)."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        from .models import Collection

        return list(
            Collection.objects.filter(is_published=True, product_count__gt=0)
            .select_related("category").order_by("category__name", "position")
        )

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return obj.updated_at

    def get_latest_lastmod(self):
        return max((c.updated_at for c in self.items()), default=None)


class StaticViewSitemap(CanonicalSitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return [
            "catalog:index",
            "pages:trust",
            "pages:about",
            "pages:intellectual_property",
            "pages:refunds",
            "pages:privacy",
            "pages:terms",
            "orders:track",
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        if item == "catalog:index":
            return _indexable_products().aggregate(last=Max("last_synced"))["last"]
        return None

    def get_latest_lastmod(self):
        return self.lastmod("catalog:index")


SITEMAPS = {
    "productos": ProductSitemap,
    "categorias": CategorySitemap,
    "colecciones": CollectionSitemap,
    "paginas": StaticViewSitemap,
}


def sitemap_index(request):
    """Índice de sitemaps con URLs sobre el host canónico (la vista index de
    Django usaría el host de la petición)."""
    base = site_base_url(request)
    entries = []
    for section, sitemap_class in SITEMAPS.items():
        location = base + reverse("sitemap_section", kwargs={"section": section})
        if sitemap_class is ProductSitemap:
            for page, last_mod in enumerate(ProductSitemap().page_lastmods(), start=1):
                entries.append({"location": location if page == 1 else f"{location}?p={page}", "last_mod": last_mod})
            continue
        entries.append({"location": location, "last_mod": sitemap_class().get_latest_lastmod()})
    return TemplateResponse(request, "sitemap_index.xml", {"sitemaps": entries}, content_type="application/xml")
