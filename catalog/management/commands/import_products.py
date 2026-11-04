"""
Management command: bulk import products from Dropi with quality filters.

Usage examples:

  # Dry run — count how many products would pass filters, no DB writes
  python manage.py import_products --dry-run

  # Real import with default quality filters
  python manage.py import_products

  # Adjust filters
  python manage.py import_products --min-profit 30000 --min-stock 10 --min-price 80000

  # Import only a specific category, max 200 products
  python manage.py import_products --category "Hogar" --limit 200

  # Re-run later: skip products already in DB, only import new ones
  python manage.py import_products --skip-existing

  # Slower crawl to be gentle on Dropi API
  python manage.py import_products --delay 1.0

  # Traer productos nuevos de las categorías prioritarias, con galería
  # completa, y publicarlos si tienen suficientes imágenes válidas
  python manage.py import_products --skip-existing --store-category belleza,tecnologia \\
      --with-gallery --activate --limit 300
"""
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection, OperationalError as DjOperationalError

from dropi_client import DropiAPIError, DropiClient

from django.conf import settings

import requests
from django.utils import timezone

from catalog.models import Product
from catalog.services.categorization import classify_product_text
from catalog.services.dropi_import import upsert_product
from catalog.services.gallery_sync import RateLimiter, fetch_gallery
from catalog.services.pricing import compute_price
from catalog.services.product_filters import FilterOptions, check_product
from catalog.services.ranking import compute_rank_score

DEFAULT_PAGE_SIZE = 50
MAX_RETRIES = 3
RETRY_BACKOFF = 5   # seconds between retries
READ_TIMEOUT = 60   # seconds — Dropi API can be slow
RATE_LIMIT_SLEEP = 30  # seconds to sleep when API returns 429


class Command(BaseCommand):
    help = "Importa productos desde Dropi aplicando filtros de calidad."

    def add_arguments(self, parser):
        # ── Filters ──
        parser.add_argument(
            "--min-profit",
            type=int,
            default=25_000,
            metavar="MXN",
            help="Ganancia mínima absoluta (suggested - cost). Default: 25000",
        )
        parser.add_argument(
            "--min-stock",
            type=int,
            default=5,
            metavar="UNITS",
            help="Stock mínimo en unidades. Default: 5",
        )
        parser.add_argument(
            "--min-price",
            type=int,
            default=0,
            metavar="MXN",
            help="Precio mínimo calculado (0 = sin límite, importa todo). Default: 0",
        )
        parser.add_argument(
            "--no-require-images",
            action="store_true",
            help="Permite importar productos sin imágenes.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Omite productos que ya existen en la DB (solo importa nuevos).",
        )
        # ── API ──
        parser.add_argument(
            "--category",
            type=str,
            default="",
            metavar="NAME",
            help="Filtrar por categoría de Dropi (ej: 'Hogar').",
        )
        parser.add_argument(
            "--min-stock-api",
            type=int,
            default=0,
            metavar="UNITS",
            help="Valor de stockmayor enviado a la API (pre-filtro en Dropi). Default: 0 (sin pre-filtro — productos con stock en variantes no se pierden).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            metavar="N",
            help="Máximo de productos a importar. 0 = sin límite.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            metavar="SECS",
            help="Pausa en segundos entre páginas de la API. Default: 0.5",
        )
        # ── Behaviour ──
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Elimina TODOS los productos y categorías existentes antes de importar.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la importación sin escribir en la DB.",
        )
        parser.add_argument(
            "--start-data",
            type=int,
            default=0,
            metavar="N",
            help="Offset inicial de startData en la API de Dropi. Útil para retomar desde un punto específico.",
        )
        parser.add_argument(
            "--store-category",
            type=str,
            default="",
            metavar="KEYS",
            help="Solo productos que la tienda clasifica en estas categorías (ej: belleza,tecnologia,salud_bienestar).",
        )
        parser.add_argument(
            "--with-gallery",
            action="store_true",
            help="Trae la galería completa del detalle de Dropi y descarta imágenes rotas (1 request extra por producto).",
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Publica los productos nuevos con galería >= CATALOG_MIN_IMAGES y stock. Requiere --with-gallery.",
        )
        # ── Imágenes IA ──
        parser.add_argument(
            "--generate-images",
            action="store_true",
            help="Genera con Gemini una imagen para productos creados/actualizados con 0 o 1 imagen (requiere GEMINI_API_KEY).",
        )
        parser.add_argument(
            "--image-delay",
            type=float,
            default=1.0,
            metavar="SECS",
            help="Pausa entre llamadas a Gemini cuando --generate-images está activo. Default: 1.0",
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _finish_product(self, product, created, client, image_session, with_gallery, activate, stats) -> None:
        """Precio, galería completa, publicación y ranking de un producto recién importado."""
        fields = {}
        if with_gallery:
            gallery = fetch_gallery(client, image_session, product.dropi_id, limiter=self.gallery_limiter)
            if not gallery.error and gallery.found:
                fields["images"] = product.images = gallery.images
                fields["gallery_synced_at"] = product.gallery_synced_at = timezone.now()
                if gallery.stock is not None:
                    fields["stock"] = product.stock = gallery.stock
            if len(product.images or []) < settings.CATALOG_MIN_IMAGES:
                stats["few_images"] += 1
            elif activate and created and product.stock > 0:
                fields["is_active"] = product.is_active = True
                stats["activated"] += 1

        if not product.price_locked:
            decision = compute_price(product.cost, product.suggested_price, product.category)
            fields["price"] = product.price = decision.price
            fields["pricing_status"] = product.pricing_status = decision.status
        fields["rank_score"] = compute_rank_score(product)
        Product.objects.filter(pk=product.pk).update(**fields)

    def _fetch_page(self, client: DropiClient, page: int, page_size: int, opts: dict) -> list:
        """Fetch one page from Dropi with retry/backoff logic."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.get_products(
                    page=page,
                    page_size=page_size,
                    category=opts["category"],
                )
                objects = resp.get("objects") or []
                if isinstance(objects, dict):
                    return objects.get("products") or objects.get("data") or []
                if isinstance(objects, list):
                    return objects
                return []
            except DropiAPIError as exc:
                msg = str(exc)
                if "429" in msg or "rate" in msg.lower():
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Rate limit hit — esperando {RATE_LIMIT_SLEEP}s..."
                        )
                    )
                    time.sleep(RATE_LIMIT_SLEEP)
                elif attempt < MAX_RETRIES:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Error API (intento {attempt}/{MAX_RETRIES}): {exc} "
                            f"— reintentando en {RETRY_BACKOFF}s..."
                        )
                    )
                    time.sleep(RETRY_BACKOFF)
                else:
                    raise
        return []

    # ── Main ─────────────────────────────────────────────────────────────────

    def _generate_image(self, product, stats: dict) -> None:
        """Best-effort Gemini image generation for a just-imported product. Never raises."""
        from catalog.services.image_generation import ensure_product_image

        try:
            status = ensure_product_image(product)
        except Exception as exc:
            stats["images_errors"] += 1
            self.stdout.write(self.style.ERROR(f"    imagen IA error [{product.pk}]: {exc}"))
            return

        if status == "generated":
            stats["images_generated"] += 1
        elif status == "flagged":
            stats["images_flagged"] += 1
        elif status == "error":
            stats["images_errors"] += 1

    def handle(self, *args, **options):
        # Fix Windows cp1252 crash on Unicode product names
        if hasattr(self.stdout, "_out") and hasattr(self.stdout._out, "reconfigure"):
            try:
                self.stdout._out.reconfigure(errors="replace")
            except Exception:
                pass

        dry_run = options["dry_run"]
        flush = options["flush"]
        limit = options["limit"]
        delay = options["delay"]

        # ── Flush existing catalog ────────────────────────────────────────────
        if flush and not dry_run:
            from catalog.models import Category
            prod_count = Product.objects.count()
            cat_count = Category.objects.count()
            Product.objects.all().delete()   # cascade-deletes reviews
            Category.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"  Flush: eliminados {prod_count} producto(s) y {cat_count} categoría(s).\n"
                )
            )

        filter_opts = FilterOptions(
            min_profit=settings.MIN_PRODUCT_PROFIT,
            min_stock=options["min_stock"],
            min_price=options["min_price"],
            require_images=not options["no_require_images"],
            skip_existing=options["skip_existing"],
            markup_factor=settings.PRODUCT_MARKUP_FACTOR,
        )

        api_opts = {
            "category": options["category"],
            "min_stock_api": options["min_stock_api"],
        }

        mode_label = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{mode_label}Importación masiva desde Dropi"
            )
        )
        price_filter_label = f"precio>${filter_opts.min_price:,}" if filter_opts.min_price > 0 else "precio=todo"
        self.stdout.write(
            f"  Filtros activos: stock>={filter_opts.min_stock}  "
            f"{price_filter_label}  "
            f"imagenes={'si' if filter_opts.require_images else 'no'}  "
            f"skip_existing={'si' if filter_opts.skip_existing else 'no'}"
        )
        self.stdout.write("  Precio final: catalog/services/pricing.py (margen por categoría, tope de mercado)\n")

        client = DropiClient()
        image_session = requests.Session()
        # Dropi tolera ~6 requests/min; el detalle de cada producto pasa por aquí.
        self.gallery_limiter = RateLimiter(0.1)
        store_categories = {c.strip() for c in options["store_category"].split(",") if c.strip()}
        with_gallery = options["with_gallery"]
        activate = options["activate"] and with_gallery

        start_data = options["start_data"]  # real byte-offset into Dropi's result set
        pages_processed = 0
        page_size = DEFAULT_PAGE_SIZE

        generate_images = options["generate_images"]
        image_delay = options["image_delay"]

        stats = {
            "fetched": 0,
            "filtered_out": 0,
            "skipped_existing": 0,
            "created": 0,
            "updated": 0,
            "refreshed_stale": 0,
            "deactivated_stale": 0,
            "errors": 0,
            "images_generated": 0,
            "images_flagged": 0,
            "images_errors": 0,
            "other_category": 0,
            "too_cheap": 0,
            "activated": 0,
            "few_images": 0,
        }
        reject_reasons: dict[str, int] = {}

        try:
            while True:
                # ── Fetch page ────────────────────────────────────────────
                products_list = self._fetch_page_with_stockmayor(
                    client, start_data, page_size, api_opts
                )

                if not products_list:
                    break

                # Force-close then reopen DB conn — API fetch may have left it idle too long
                connection.close()
                pages_processed += 1

                stats["fetched"] += len(products_list)

                # ── Process each product ──────────────────────────────────
                for raw in products_list:
                    if limit and (stats["created"] + stats["updated"]) >= limit:
                        break

                    dropi_id = raw.get("id") or raw.get("products_id")

                    try:
                        existing_product = Product.objects.filter(dropi_id=dropi_id).first()
                    except DjOperationalError:
                        connection.close()
                        existing_product = Product.objects.filter(dropi_id=dropi_id).first()

                    # skip-existing check
                    if filter_opts.skip_existing and existing_product:
                        stats["skipped_existing"] += 1
                        continue

                    # Quality filter
                    result = check_product(raw, filter_opts)
                    if not result.passed:
                        stats["filtered_out"] += 1
                        reject_reasons[result.reason] = (
                            reject_reasons.get(result.reason, 0) + 1
                        )
                        # Existing product no longer meets the quality bar
                        # (stock dropped, images removed upstream, etc.) —
                        # refresh its stock/cost/variants/images from Dropi
                        # and deactivate it, instead of leaving stale data
                        # untouched in the DB.
                        if existing_product and not dry_run:
                            try:
                                upsert_product(raw)
                            except DjOperationalError:
                                connection.close()
                                try:
                                    upsert_product(raw)
                                except Exception as exc:
                                    self.stdout.write(
                                        self.style.ERROR(f"  ERROR [{dropi_id}] refresh: {exc}")
                                    )
                                    stats["errors"] += 1
                                    continue
                            except Exception as exc:
                                self.stdout.write(
                                    self.style.ERROR(f"  ERROR [{dropi_id}] refresh: {exc}")
                                )
                                stats["errors"] += 1
                                continue
                            stats["refreshed_stale"] += 1
                            if existing_product.is_active:
                                Product.objects.filter(pk=existing_product.pk).update(is_active=False)
                                stats["deactivated_stale"] += 1
                        continue

                    name = (raw.get("name") or "").strip()
                    first_cat = (raw.get("categories") or [{}])[0]
                    category_key = classify_product_text(
                        name=name,
                        description=raw.get("description") or "",
                        dropi_category_name=first_cat.get("name", "") if isinstance(first_cat, dict) else "",
                    ).category_key
                    if store_categories and category_key not in store_categories:
                        stats["other_category"] += 1
                        continue

                    price = compute_price(
                        raw.get("sale_price") or raw.get("price") or 0,
                        raw.get("suggested_price") or 0,
                        category_key,
                    ).price
                    if price < settings.CATALOG_MIN_PRICE:
                        stats["too_cheap"] += 1
                        continue

                    if not dry_run:
                        try:
                            product, created = upsert_product(raw)
                        except DjOperationalError:
                            # DB connection dropped mid-page — reconnect and retry once
                            connection.close()
                            try:
                                product, created = upsert_product(raw)
                            except Exception as exc:
                                self.stdout.write(
                                    self.style.ERROR(f"  ERROR [{dropi_id}] {name}: {exc}")
                                )
                                stats["errors"] += 1
                                continue
                        except Exception as exc:
                            self.stdout.write(
                                self.style.ERROR(f"  ERROR [{dropi_id}] {name}: {exc}")
                            )
                            stats["errors"] += 1
                            continue

                        self._finish_product(product, created, client, image_session, with_gallery, activate, stats)

                        if created:
                            stats["created"] += 1
                            self.stdout.write(
                                f"  + [{dropi_id}] {name[:60]}  "
                                f"precio=${price:,.0f}"
                            )
                        else:
                            stats["updated"] += 1

                        if generate_images:
                            self._generate_image(product, stats)
                            if image_delay > 0:
                                time.sleep(image_delay)
                    else:
                        # dry-run: count as "would create/update"
                        # skip DB query — connection may be stale after long API crawl
                        stats["created"] += 1
                        self.stdout.write(
                            f"  ~ [{dropi_id}] {name[:60]}  "
                            f"precio=${price:,.0f}"
                        )

                # ── Break conditions ──────────────────────────────────────
                if limit and (stats["created"] + stats["updated"]) >= limit:
                    self.stdout.write(
                        self.style.WARNING(f"\n  Límite de {limit} productos alcanzado.")
                    )
                    break

                # Advance offset by the number of items actually returned.
                # Break only when the API returns nothing (true last page).
                start_data += len(products_list)
                if delay > 0:
                    time.sleep(delay)

        except DropiAPIError as exc:
            self.stdout.write(
                self.style.ERROR(f"\nError fatal de API Dropi: {exc}")
            )

        # ── Summary ──────────────────────────────────────────────────────────
        action = "importarían" if dry_run else "importados"
        self.stdout.write("\n" + "─" * 56)
        self.stdout.write(
            self.style.SUCCESS(
                f"  Páginas procesadas : {pages_processed}"
            )
        )
        self.stdout.write(f"  Productos vistos   : {stats['fetched']}")
        self.stdout.write(f"  Filtrados (rechaz.): {stats['filtered_out']}")
        if stats["refreshed_stale"]:
            self.stdout.write(
                f"  Refrescados (stale): {stats['refreshed_stale']} "
                f"({stats['deactivated_stale']} desactivados)"
            )
        if filter_opts.skip_existing:
            self.stdout.write(f"  Omitidos (existen) : {stats['skipped_existing']}")
        self.stdout.write(
            self.style.SUCCESS(
                f"  {'Se ' if dry_run else ''}Creados            : {stats['created']}"
            )
        )
        self.stdout.write(f"  Actualizados       : {stats['updated']}")
        if stats["errors"]:
            self.stdout.write(self.style.ERROR(f"  Errores            : {stats['errors']}"))
        if store_categories:
            self.stdout.write(f"  Otra categoría     : {stats['other_category']}")
            self.stdout.write(f"  Precio muy bajo    : {stats['too_cheap']}")
        if with_gallery:
            self.stdout.write(
                f"  Publicados         : {stats['activated']}  "
                f"(con menos de {settings.CATALOG_MIN_IMAGES} imágenes válidas: {stats['few_images']})"
            )
        if generate_images:
            self.stdout.write(
                f"  Imágenes IA        : {stats['images_generated']} generadas, "
                f"{stats['images_flagged']} marcadas p/revisión, {stats['images_errors']} errores"
            )

        if reject_reasons:
            self.stdout.write("\n  Top razones de rechazo:")
            for reason, count in sorted(
                reject_reasons.items(), key=lambda x: -x[1]
            )[:8]:
                self.stdout.write(f"    · {reason}: {count}")

        self.stdout.write("─" * 56 + "\n")

    def _fetch_page_with_stockmayor(
        self, client: DropiClient, start_data: int, page_size: int, api_opts: dict
    ) -> list:
        """
        Fetch a page from Dropi, injecting stockmayor and the correct startData
        offset into the payload via a temporary monkey-patch on _post.
        """
        import functools

        min_stock_api = api_opts.get("min_stock_api", 5)
        category = api_opts.get("category", "")

        original_post = client._post

        @functools.wraps(original_post)
        def patched_post(path, payload):
            if "products/index" in path:
                payload["stockmayor"] = min_stock_api
                # Override startData so we use the real offset, not page*page_size
                payload["startData"] = start_data
            return original_post(path, payload)

        client._post = patched_post
        try:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # page=0 so client computes startData=0; our patch overrides it
                    resp = client.get_products(
                        page=0,
                        page_size=page_size,
                        category=category,
                    )
                    objects = resp.get("objects") or []
                    if isinstance(objects, dict):
                        return objects.get("products") or objects.get("data") or []
                    if isinstance(objects, list):
                        return objects
                    return []
                except DropiAPIError as exc:
                    msg = str(exc)
                    if "429" in msg or "rate" in msg.lower():
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Rate limit — esperando {RATE_LIMIT_SLEEP}s..."
                            )
                        )
                        time.sleep(RATE_LIMIT_SLEEP)
                    elif attempt < MAX_RETRIES:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Error API (intento {attempt}/{MAX_RETRIES}): {exc} "
                                f"— reintentando en {RETRY_BACKOFF}s..."
                            )
                        )
                        time.sleep(RETRY_BACKOFF)
                    else:
                        raise
        finally:
            client._post = original_post

        return []
