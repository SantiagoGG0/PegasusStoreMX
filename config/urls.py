from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.views.decorators.cache import cache_page
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from catalog.sitemaps import SITEMAPS, sitemap_index
from catalog.views import robots_txt


def handler429(request, exception=None):
    return HttpResponse(
        "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
        status=429,
        content_type="text/plain",
    )


handler429 = handler429  # noqa: F811

# El sitemap de productos tarda varios segundos en generarse (~35k URLs):
# se cachea 1 h (caché en archivos, compartida) para responder en
# milisegundos. Con 6 h, una colección publicada en el admin tardaba medio día
# en aparecer.
SITEMAP_CACHE_SECONDS = 60 * 60

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("sitemap.xml", cache_page(SITEMAP_CACHE_SECONDS)(sitemap_index), name="sitemap"),
    path(
        "sitemap-<section>.xml",
        cache_page(SITEMAP_CACHE_SECONDS)(sitemap),
        {"sitemaps": SITEMAPS, "template_name": "catalog/sitemap_section.xml"},
        name="sitemap_section",
    ),
    path("robots.txt", robots_txt, name="robots"),
    path("", include("catalog.urls", namespace="catalog")),
    path("carrito/", include("cart.urls", namespace="cart")),
    path("pedidos/", include("orders.urls", namespace="orders")),
    path("", include("pages.urls", namespace="pages")),
    # Redirect — rediseño 2026: el centro de ayuda ya no existe como página
    # propia; su contenido vive en el FAQ del inicio. (El redirect de
    # "Sobre nosotros" hacia Confianza vive en pages/urls.py, bajo /legal/,
    # que es donde realmente estaba montado antes.)
    path("ayuda/", RedirectView.as_view(url="/#faq", permanent=True)),
    # Rediseño 2026 — cuentas de cliente y "mis pedidos" ya no existen; el
    # seguimiento es por guía o teléfono (/pedidos/seguimiento/).
    re_path(r"^cuenta(?:/.*)?$", RedirectView.as_view(url="/", permanent=True)),
    path("pedidos/mis-pedidos/", RedirectView.as_view(url="/pedidos/seguimiento/", permanent=True)),
    # Enlaces mágicos de correos antiguos ("ver mis pedidos").
    path("pedidos/acceso/<str:token>/", RedirectView.as_view(url="/pedidos/seguimiento/", permanent=True)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve media files in production when using local/volume storage (no S3/Cloudinary)
if not settings.DEBUG and not getattr(settings, 'USE_S3', False) and not getattr(settings, 'USE_CLOUDINARY', False):
    from django.views.static import serve
    from django.urls import re_path
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
