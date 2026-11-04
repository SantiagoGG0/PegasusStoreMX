"""
Feed de productos para Google Merchant Center (RSS 2.0 + namespace g:).

Con este feed los productos aparecen gratis en Google Shopping ("fichas
gratuitas") y se pueden usar en campañas de Shopping / Performance Max.
Merchant Center lo descarga una vez al día desde /feeds/google-merchant.xml.

Incluye solo productos activos, con stock, con al menos una foto y que se
pueden usar en campañas (sin exclusión SEO/ads).

Generar 40.000 productos tarda más que el límite de gunicorn (120 s), así que
el feed se escribe en un archivo en segundo plano (por lotes, sin cargar todo
en memoria) y se sirve ese archivo; se regenera cuando tiene más de 12 horas.

El disco del contenedor se borra en cada despliegue o reinicio: cada versión
terminada se guarda además comprimida en la base de datos (FeedSnapshot) y,
si el archivo local falta, se restaura de ahí mientras se genera uno nuevo.
Así Merchant Center siempre recibe la última versión buena, nunca un error.

Los casi duplicados (canonical_product) no van: Merchant los marcaba como
productos repetidos (5.353 títulos iguales).
"""
import gzip
import io
import logging
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from xml.sax.saxutils import escape

from django.db import DatabaseError, connection
from django.utils import timezone
from django.http import FileResponse, HttpResponse
from django.utils.text import Truncator
from django.views.decorators.http import require_http_methods

from config.site import absolute_url

from .models import LISTING_EXCLUSIONS, FeedSnapshot, Product
from .seo import product_brand, product_image_urls, product_name, product_text

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
MAX_ADDITIONAL_IMAGES = 10
FEED_FILE = Path(tempfile.gettempdir()) / "pegasus-google-merchant.xml"
FEED_MAX_AGE = 12 * 3600
SNAPSHOT_NAME = "google-merchant"
_lock = threading.Lock()
_generating = False


# Categoría de la tienda → taxonomía de Google (texto en inglés, que Merchant
# acepta igual que el ID). Sin ella, Google adivina dónde mostrar el producto.
# "Otros" y bienestar íntimo no llevan categoría.
GOOGLE_CATEGORY = {
    "hogar": "Home & Garden",
    "cocina": "Home & Garden > Kitchen & Dining",
    "belleza": "Health & Beauty > Personal Care",
    "tecnologia": "Electronics",
    "salud_bienestar": "Health & Beauty > Health Care",
    "juguetes": "Toys & Games",
    "deporte_fitness": "Sporting Goods > Exercise & Fitness",
    "moda_accesorios": "Apparel & Accessories",
    "herramientas": "Hardware > Tools",
    "fiesta_pinateria": "Arts & Entertainment > Party & Celebration > Party Supplies",
    "papeleria": "Office Supplies",
    "mascotas": "Animals & Pet Supplies > Pet Supplies",
    "vehiculos": "Vehicles & Parts > Vehicle Parts & Accessories",
    "bebes": "Baby & Toddler",
    "seguridad": "Home & Garden > Business & Home Security",
}


def _google_category(product) -> str:
    if not product.category_id:
        return ""
    return GOOGLE_CATEGORY.get(str(product.category.dropi_id).split(":", 1)[-1], "")


def _tag(name: str, value) -> str:
    return f"<g:{name}>{escape(str(value))}</g:{name}>" if value not in (None, "") else ""


def feed_item(product, request) -> str:
    images = product_image_urls(product, request, limit=1 + MAX_ADDITIONAL_IMAGES)
    title = Truncator(product_name(product)).chars(150, truncate="…")
    if not title or not images:
        return ""   # Merchant rechaza ítems sin título o sin foto
    # Solo el inicio: limpiar descripciones completas de 40.000 productos hacía
    # el feed demasiado lento y pesado (Shopping muestra pocas líneas).
    description = product_text(product, limit=3000) or title
    parts = [
        _tag("id", product.dropi_id),
        f"<title>{escape(title)}</title>",
        f"<description>{escape(Truncator(description).chars(1000, truncate='…'))}</description>",
        f"<link>{escape(absolute_url(request, product.get_absolute_url()))}</link>",
        _tag("image_link", images[0]),
        *(_tag("additional_image_link", url) for url in images[1:]),
        _tag("availability", "in_stock"),
        _tag("price", f"{product.price:.2f} MXN"),
        _tag("condition", "new"),
        _tag("brand", product_brand(product)),
        _tag("identifier_exists", "no"),
        _tag("product_type", product.category.name if product.category else ""),
        _tag("google_product_category", _google_category(product)),
    ]
    # El envío depende de la ciudad: se declara solo cuando es gratis en todo
    # el país; el resto usa la configuración de envío de la cuenta.
    if product.likely_free_shipping:
        parts.append("<g:shipping><g:country>MX</g:country><g:price>0.00 MXN</g:price></g:shipping>")
    return "<item>" + "".join(parts) + "</item>\n"


def feed_queryset():
    return (
        Product.objects.filter(is_active=True, stock__gt=0, image_flagged=False, price__gt=0)
        .exclude(seo_exclusion__in=LISTING_EXCLUSIONS)
        .exclude(images=[])
        .filter(canonical_product__isnull=True)
        .select_related("category")
        .prefetch_related("custom_images")
        .order_by("pk")
    )


def feed_chunks(request):
    """El feed completo, por partes (para escribirlo al archivo sin cargarlo entero)."""
    yield (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n<channel>\n'
        "<title>Pegasus Store</title>\n"
        f"<link>{escape(absolute_url(request, '/'))}</link>\n"
        "<description>Productos de Pegasus Store con pago contra entrega en México</description>\n"
    )
    last_pk = 0
    while True:
        batch = list(feed_queryset().filter(pk__gt=last_pk)[:BATCH_SIZE])
        if not batch:
            break
        for product in batch:
            yield feed_item(product, request)
        last_pk = batch[-1].pk
    yield "</channel>\n</rss>\n"


def write_feed(request, path: Path = FEED_FILE) -> int:
    """Escribe el feed al archivo local y guarda una copia comprimida en la
    base de datos. Devuelve cuántos productos tiene."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    count = 0
    with open(tmp, "w", encoding="utf-8") as fh:
        for chunk in feed_chunks(request):
            if chunk.startswith("<item>"):
                count += 1
            fh.write(chunk)
    os.replace(tmp, path)
    _save_snapshot(path, count)
    return count


def _save_snapshot(path: Path, count: int) -> None:
    # Comprime por bloques: el servidor tiene 0,5 GB y el feed pesa ~70 MB.
    buffer = io.BytesIO()
    with open(path, "rb") as src, gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
    try:
        FeedSnapshot.objects.update_or_create(
            name=SNAPSHOT_NAME,
            defaults={"content_gz": buffer.getvalue(), "item_count": count, "created_at": timezone.now()},
        )
    except DatabaseError:
        logger.exception("No se pudo guardar la copia del feed en la base de datos")


def _restore_snapshot(path: Path | None = None) -> bool:
    """Si el archivo local no existe (despliegue o reinicio), lo recrea desde la
    última copia de la base de datos, con su fecha real para que se regenere
    cuando corresponda."""
    path = path or FEED_FILE
    try:
        snapshot = FeedSnapshot.objects.filter(name=SNAPSHOT_NAME).first()
    except DatabaseError:
        logger.exception("No se pudo leer la copia del feed")
        return False
    if not snapshot:
        return False
    tmp = path.with_name(f"{path.name}.{os.getpid()}.restore")
    with gzip.GzipFile(fileobj=io.BytesIO(bytes(snapshot.content_gz)), mode="rb") as src, open(tmp, "wb") as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
    os.replace(tmp, path)
    stamp = snapshot.created_at.timestamp()
    os.utime(path, (stamp, stamp))
    return True


def _regenerate_in_background(request) -> None:
    global _generating
    with _lock:
        if _generating:
            return
        _generating = True

    def run():
        global _generating
        try:
            write_feed(request)
        except Exception:
            logger.exception("No se pudo generar el feed de Google Merchant")
        finally:
            connection.close()
            _generating = False

    threading.Thread(target=run, name="google-merchant-feed", daemon=True).start()


@require_http_methods(["GET", "HEAD"])
def google_merchant_feed(request):
    if not FEED_FILE.exists():
        _restore_snapshot()
    fresh = FEED_FILE.exists() and time.time() - FEED_FILE.stat().st_mtime < FEED_MAX_AGE
    if not fresh:
        _regenerate_in_background(request)
    if FEED_FILE.exists():
        return FileResponse(open(FEED_FILE, "rb"), content_type="application/xml; charset=utf-8")
    response = HttpResponse("El feed se está generando; vuelve a intentar en unos minutos.", status=503)
    response["Retry-After"] = "600"
    return response
