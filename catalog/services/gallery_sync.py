"""
Galería completa desde Dropi.

El listado `products/index` solo trae la foto principal de cada producto; la
galería completa está en el detalle `products/v2/{id}` (campo `photos`). Este
servicio pide el detalle, arma la galería en el mismo orden que Dropi y
descarta las imágenes que ya no existen en el CDN (CloudFront responde 403 a
los objetos borrados).

`fetch_gallery` no toca la base de datos: es seguro llamarla desde hilos.
Dropi responde 429 si se le pide demasiado rápido; todos los hilos comparten
un `RateLimiter` que espacia los requests y, ante un 429, frena a todos.
"""
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal

import requests

from dropi_client import DropiAPIError, DropiClient

from .dropi_import import parse_images, parse_stock

logger = logging.getLogger(__name__)

MAX_RETRIES = 6
RETRY_BACKOFF = 5
RATE_LIMIT_SLEEP = 20    # primera pausa ante un 429; se duplica en cada 429 seguido
IMAGE_TIMEOUT = 15
IMAGE_CHECK_WORKERS = 8   # las fotos están en CloudFront, no cuentan para el límite de Dropi
# Respuestas de Dropi que significan "este producto no se puede obtener": no
# es un fallo de red, reintentar solo gasta cupo (un producto así se intentaba
# decenas de veces y volvía al principio de la cola).
_GONE_MESSAGES = ("404", "no existe", "not found", "error al obtener el producto")
_IMAGE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PegasusStore-ImageCheck/1.0)"}


class RateLimiter:
    """Espaciado entre requests a Dropi, compartido entre hilos y adaptativo:
    cada 429 duplica el espaciado (hasta MAX_INTERVAL) y cada request exitoso
    lo reduce un poco hacia el ritmo inicial. Dropi no publica su límite; así
    el comando converge solo al ritmo que tolera."""

    MAX_INTERVAL = 60.0

    def __init__(self, per_second: float):
        self.base_interval = 1.0 / per_second if per_second > 0 else 0.0
        self.interval = self.base_interval
        self._next = 0.0
        self._lock = threading.Lock()

    def success(self) -> None:
        with self._lock:
            self.interval = max(self.base_interval, self.interval * 0.85)  # ~10 respuestas OK para volver al ritmo base

    def throttled(self) -> None:
        with self._lock:
            self.interval = min(self.MAX_INTERVAL, max(self.interval * 2, 1.0))

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + self.interval
        if start > now:
            time.sleep(start - now)

    def pause(self, seconds: float) -> None:
        with self._lock:
            self._next = max(self._next, time.monotonic() + seconds)


@dataclass
class GalleryResult:
    dropi_id: int
    found: bool = True                 # False = Dropi ya no tiene el producto
    images: list = field(default_factory=list)
    broken: int = 0                    # imágenes de Dropi que el CDN no sirve
    unchecked: int = 0                 # no se pudieron verificar (timeout/red): se conservan
    stock: int | None = None
    cost: Decimal | None = None
    suggested: Decimal | None = None
    error: str = ""


def _image_ok(session: requests.Session, url: str) -> bool | None:
    """True = la imagen existe, False = rota, None = no se pudo verificar."""
    try:
        resp = session.head(url, timeout=IMAGE_TIMEOUT, allow_redirects=True, headers=_IMAGE_HEADERS)
        if resp.status_code == 405:  # algunos orígenes no aceptan HEAD
            resp = session.get(url, timeout=IMAGE_TIMEOUT, stream=True, headers=_IMAGE_HEADERS)
            resp.close()
    except requests.RequestException:
        return None
    if resp.status_code in (403, 404, 410):
        return False
    if resp.status_code != 200:
        return None
    content_type = resp.headers.get("Content-Type", "")
    return content_type.startswith("image/") or content_type in ("", "application/octet-stream", "binary/octet-stream")


def _get_detail(client: DropiClient, dropi_id: int, limiter: RateLimiter | None) -> dict | None:
    rate_limited = 0
    for attempt in range(1, MAX_RETRIES + 1):
        if limiter:
            limiter.wait()
        try:
            resp = client.get_product(dropi_id)
            if limiter:
                limiter.success()
            detail = resp.get("objects") or {}
            if isinstance(detail, list):
                detail = detail[0] if detail else {}
            return detail or None
        except DropiAPIError as exc:
            msg = str(exc)
            if any(m in msg.lower() for m in _GONE_MESSAGES):
                return None
            if attempt == MAX_RETRIES:
                raise
            if "429" in msg:
                pause = RATE_LIMIT_SLEEP * 2 ** rate_limited
                rate_limited += 1
                if limiter:
                    limiter.throttled()
                    limiter.pause(pause)
                else:
                    time.sleep(pause)
            else:
                time.sleep(RETRY_BACKOFF)
    return None


def fetch_gallery(
    client: DropiClient,
    session: requests.Session,
    dropi_id: int,
    verify: bool = True,
    limiter: RateLimiter | None = None,
) -> GalleryResult:
    result = GalleryResult(dropi_id=dropi_id)
    try:
        detail = _get_detail(client, dropi_id, limiter)
    except DropiAPIError as exc:
        result.error = str(exc)[:200]
        return result
    if detail is None or detail.get("active") is False:
        result.found = False
        return result

    unique = list({img["url"]: img for img in parse_images(detail)}.values())
    if verify and unique:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(IMAGE_CHECK_WORKERS, len(unique))) as pool:
            checks = list(pool.map(lambda img: _image_ok(session, img["url"]), unique))
    else:
        checks = [True] * len(unique)
    for img, ok in zip(unique, checks):
        if ok is False:
            result.broken += 1
            continue
        if ok is None:
            result.unchecked += 1
        result.images.append(img)

    result.stock = parse_stock(detail)
    cost = detail.get("sale_price") or detail.get("price")
    if cost:
        result.cost = Decimal(str(cost))
    if detail.get("suggested_price"):
        result.suggested = Decimal(str(detail["suggested_price"]))
    return result


ON_VIEW_TIMEOUT = 3          # segundos: la ficha no puede quedar esperando a Dropi
ON_VIEW_RETRY_SECONDS = 86400
# Comparte el límite de Dropi (~6 requests/min) con catalog_worker: como mucho
# 1 request cada 30 s por proceso, y nunca para robots (Google recorre miles de
# fichas y se comería el cupo).
ON_VIEW_MIN_INTERVAL = 30
BOT_UA = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|preview|lighthouse|headless|curl|python-requests", re.I)


def is_bot(request) -> bool:
    return bool(BOT_UA.search(request.META.get("HTTP_USER_AGENT", "")))


def ensure_gallery_on_view(product, request=None) -> None:
    """Galería completa a partir de la primera vez que alguien abre la ficha.

    Si el producto todavía no pasó por `sync_galleries`, pide su detalle a
    Dropi (un request, máx. ON_VIEW_TIMEOUT s) y guarda las fotos. Por defecto
    lo hace en segundo plano (settings.GALLERY_ON_VIEW_ASYNC): la ficha no
    espera a Dropi (cuenta para Core Web Vitals) y el siguiente visitante ya
    ve todas las fotos. No verifica cada imagen (eso lo hace el proceso de
    fondo, que sigue tomando este producto porque gallery_synced_at queda
    vacío; las rotas las oculta el navegador). Un intento por producto al día
    y nunca rompe la ficha: cualquier error deja las fotos que había.
    """
    from django.conf import settings
    from django.core.cache import cache

    if not settings.GALLERY_ON_VIEW or product.gallery_synced_at or not product.dropi_id:
        return
    if request is not None and is_bot(request):
        return
    if not cache.add(f"gallery-on-view:{product.pk}", 1, ON_VIEW_RETRY_SECONDS):
        return
    if not cache.add("gallery-on-view:throttle", 1, ON_VIEW_MIN_INTERVAL):
        cache.delete(f"gallery-on-view:{product.pk}")   # se intenta en otra visita
        return
    if getattr(settings, "GALLERY_ON_VIEW_ASYNC", True):
        threading.Thread(
            target=_fetch_on_view, args=(product.pk, product.dropi_id, len(product.images or [])),
            name="gallery-on-view", daemon=True,
        ).start()
    else:
        product.images = _fetch_on_view(product.pk, product.dropi_id, len(product.images or [])) or product.images


def _fetch_on_view(pk: int, dropi_id: int, current_count: int):
    """Trae y guarda la galería; devuelve las fotos nuevas o None."""
    from django.db import connection

    from catalog.models import Product

    try:
        try:
            resp = DropiClient().get_product(dropi_id, timeout=ON_VIEW_TIMEOUT)
        except Exception as exc:  # 429, timeout, red: se queda con lo que había
            logger.info("Galería al ver ficha %s: %s", dropi_id, exc)
            return None
        detail = resp.get("objects") or {}
        if isinstance(detail, list):
            detail = detail[0] if detail else {}
        images = []
        for img in parse_images(detail or {}):
            if img not in images:
                images.append(img)
        if len(images) > current_count:
            Product.objects.filter(pk=pk).update(images=images)
            return images
        return None
    finally:
        if threading.current_thread() is not threading.main_thread() and                 threading.current_thread().name == "gallery-on-view":
            connection.close()



# ── Cola y aplicación (usadas por sync_galleries y catalog_worker) ───────────

AUTO_REASONS = {"no_existe", "sin_imagenes", "sin_stock"}


def gallery_queue(stale_days: int = 30, include_inactive: bool = True, category: str = "",
                  shard: int = 0, shards: int = 1):
    """Productos por traer/verificar galería, en orden: nunca sincronizados
    primero, luego categorías prioritarias, luego los de más relevancia.
    Incluye los despublicados automáticamente (y los nuevos pendientes de
    fotos, que entran como inactive_reason="sin_imagenes")."""
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Case, F, IntegerField, Q, Value, When
    from django.utils import timezone

    from catalog.models import Product

    cutoff = timezone.now() - timedelta(days=stale_days)
    qs = Product.objects.select_related("category").filter(
        Q(gallery_synced_at__isnull=True) | Q(gallery_synced_at__lt=cutoff)
    )
    if include_inactive:
        qs = qs.filter(Q(is_active=True) | Q(inactive_reason__in=AUTO_REASONS))
    else:
        qs = qs.filter(is_active=True)
    if category:
        qs = qs.filter(category__dropi_id=f"store:{category}")
    if shards > 1:
        # Cada token de Dropi trabaja una porción fija del catálogo.
        from django.db.models.functions import Mod

        qs = qs.annotate(shard=Mod("id", shards)).filter(shard=shard)

    priority = sorted(settings.PRICING_CATEGORY_PROFILES.items(), key=lambda kv: -kv[1].get("weight", 1.0))
    whens = [
        When(category__dropi_id=f"store:{key}", then=Value(i))
        for i, (key, profile) in enumerate(priority)
        if profile.get("weight", 1.0) > 1.0
    ]
    qs = qs.annotate(
        cat_priority=Case(*whens, default=Value(99), output_field=IntegerField()),
        # Primero los nuevos pendientes de fotos (no se ven hasta tenerlas),
        # luego los publicados y al final los despublicados (solo se revisan
        # por si volvieron).
        visible_first=Case(
            When(is_active=False, inactive_reason="sin_imagenes", gallery_synced_at__isnull=True, then=Value(0)),
            When(is_active=True, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
    )
    return qs.order_by(
        "visible_first", F("gallery_synced_at").asc(nulls_first=True), "cat_priority", "-rank_score", "id"
    )


def apply_gallery_result(product, result: GalleryResult, stats, *, reactivate: bool = True,
                         reprice: bool = True, save: bool = True) -> None:
    """Aplica el detalle de Dropi a `product` y lo guarda (si save).

    Despublica si ya no existe, no tiene fotos válidas o no tiene stock. Con
    `reactivate` publica los despublicados automáticamente (y los nuevos)
    cuando vuelven a cumplir; para publicar exige CATALOG_MIN_IMAGES fotos
    válidas, para seguir publicado basta una.
    """
    from django.conf import settings
    from django.utils import timezone

    from catalog.models import Product

    from .pricing import compute_price
    from .ranking import compute_rank_score

    if result.error:
        stats["errors"] += 1
        return

    fields = {"gallery_synced_at"}
    product.gallery_synced_at = timezone.now()
    reason = ""

    if not result.found:
        reason = "no_existe"
    else:
        stats["ok"] += 1
        before = len(product.images or [])
        stats["images_before"] += before
        stats["images_after"] += len(result.images)
        stats["broken"] += result.broken
        if len(result.images) > before:
            stats["more_images"] += 1
        if result.images != product.images:
            product.images = result.images
            fields.add("images")

        if result.stock is not None and result.stock != product.stock:
            product.stock = result.stock
            fields.add("stock")
        if result.suggested is not None and result.suggested != product.suggested_price:
            product.suggested_price = result.suggested
            fields.add("suggested_price")
        cost_changed = result.cost is not None and result.cost != product.cost
        if cost_changed:
            product.cost = result.cost
            fields.add("cost")
        # Solo si cambia el costo (o es un producto sin precio aún), para no
        # perder margen. El recálculo masivo es `manage.py reprice_catalog`.
        if reprice and not product.price_locked and (cost_changed or not product.price):
            decision = compute_price(product.cost, product.suggested_price, product.category)
            if decision.price != product.price or decision.status != product.pricing_status:
                product.price = decision.price
                product.pricing_status = decision.status
                fields |= {"price", "pricing_status"}
                stats["repriced"] += 1

        min_images = 1 if product.is_active else settings.CATALOG_MIN_IMAGES
        if len(result.images) < min_images:
            reason = "sin_imagenes"
        elif not product.stock:
            reason = "sin_stock"

    if reason and product.is_active:
        product.is_active = False
        product.inactive_reason = reason
        fields |= {"is_active", "inactive_reason"}
        stats[reason] += 1
    elif reason and not product.is_active and product.inactive_reason in AUTO_REASONS and product.inactive_reason != reason:
        product.inactive_reason = reason
        fields.add("inactive_reason")
    elif not reason and not product.is_active and reactivate and product.inactive_reason in AUTO_REASONS:
        product.is_active = True
        product.inactive_reason = ""
        fields |= {"is_active", "inactive_reason"}
        stats["reactivated"] += 1

    new_score = compute_rank_score(product)
    if new_score != product.rank_score:
        product.rank_score = new_score
        fields.add("rank_score")

    if fields & {"images", "price"}:
        product.last_synced = timezone.now()
        fields.add("last_synced")
    if save:
        Product.objects.filter(pk=product.pk).update(**{f: getattr(product, f) for f in fields})
