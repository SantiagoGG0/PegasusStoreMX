"""
Management command: catalog_worker

Sincronización continua y reanudable del catálogo con Dropi. Comparte el
límite de Dropi (~6 requests/min) entre dos trabajos intercalados y guarda el
avance después de CADA request, así un corte (PC suspendido, red) pierde a lo
sumo un producto:

  - Listado (1 de cada `--listing-every` requests): una página de 40
    productos de `products/index`. Actualiza stock, costo, sugerido y precio
    de los que ya están en la tienda; crea los que no están (si pasan los
    filtros de calidad) como pendientes de fotos. Al terminar la vuelta
    completa al catálogo de Dropi, despublica los que no aparecieron (si la
    vuelta vio al menos la mitad de los activos) y empieza otra.
  - Detalle (el resto): galería completa de un producto (nuevos y nunca
    sincronizados primero, categorías prioritarias, más relevantes). Publica
    los nuevos con CATALOG_MIN_IMAGES fotos válidas y stock; despublica sin
    fotos / sin stock / inexistentes. Ver catalog.services.gallery_sync.

La posición en el listado y los productos vistos en la vuelta actual se
guardan en --state-file.

Varios tokens (settings.DROPI_READ_TOKENS): se corre un proceso por token con
--token-index i. Cada uno trae las galerías de su porción del catálogo
(id % cantidad de tokens) con su propio cupo de Dropi; solo el token 0
recorre el listado.

Usage:
    python manage.py catalog_worker --max-minutes 60
    python manage.py catalog_worker --listing-every 2      # más stock, menos fotos
    python manage.py catalog_worker --token-index 1        # segundo token: solo galerías
"""
import json
import time
from collections import Counter
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections, connections
from django.utils import timezone

from catalog.models import Product
from catalog.services.dropi_import import upsert_product
from catalog.services.gallery_sync import RateLimiter, apply_gallery_result, fetch_gallery, gallery_queue
from catalog.services.pricing import compute_price
from catalog.services.product_filters import FilterOptions, check_product
from catalog.services.ranking import compute_rank_score
from catalog.services.stock_sync import _fetch_page, apply_listing_raw, touches_page
from dropi_client import DropiAPIError, DropiClient

PAGE_SIZE = 40  # Dropi nunca devuelve más de 40 por página
NETWORK_RETRY_SECONDS = 30
PROGRESS_EVERY = 10
NEW_PRODUCT_FILTERS = FilterOptions(min_stock=5, require_images=True)


class Command(BaseCommand):
    help = "Sync continua y reanudable: stock/precios por páginas + galerías por producto + productos nuevos."

    def add_arguments(self, parser):
        parser.add_argument("--max-minutes", type=float, default=60, help="Corta limpio tras N minutos (0 = sin límite). Default: 60")
        parser.add_argument("--listing-every", type=int, default=4, help="1 de cada N requests es una página del listado. Default: 4")
        parser.add_argument("--rps", type=float, default=0.1, help="Requests por segundo a Dropi. Default: 0.1")
        parser.add_argument("--state-file", default="logs/catalog_worker_state.json")
        parser.add_argument("--no-new-products", action="store_true", help="No crea productos que no estén en la tienda.")
        parser.add_argument("--token-index", type=int, default=0, help="Qué token de DROPI_READ_TOKENS usar (0 = DROPI_TOKEN). Default: 0")

    # ── Estado ───────────────────────────────────────────────────────────────

    def _load_state(self) -> dict:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            state["seen"] = set(state.get("seen", []))
            return state
        except (FileNotFoundError, ValueError):
            return self._new_cycle({})

    def _new_cycle(self, state: dict) -> dict:
        state.update({"cursor": 0, "seen": set(), "cycle_started": timezone.now().isoformat()})
        return state

    def _save_state(self) -> None:
        data = dict(self.state, seen=sorted(self.state["seen"]))
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self.state_path)

    # ── Main loop ────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        self.state_path = Path(opts["state_file"])
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        self.create_new = not opts["no_new_products"]
        tokens = settings.DROPI_READ_TOKENS
        self.shard, self.shards = opts["token_index"], len(tokens)
        if not 0 <= self.shard < self.shards:
            raise CommandError(f"--token-index {self.shard} fuera de rango: hay {self.shards} token(s).")
        self.does_listing = self.shard == 0
        self.client, self.session = DropiClient(tokens[self.shard]), requests.Session()
        self.limiter = RateLimiter(opts["rps"])
        self.stats = Counter()
        self.queue: list = []
        self.failed: set[int] = set()   # fallaron en esta tanda: no vuelven a la cola hasta la próxima

        deadline = time.monotonic() + opts["max_minutes"] * 60 if opts["max_minutes"] else None
        self.tag = f"[token {self.shard + 1}/{self.shards}] " if self.shards > 1 else ""
        self.stdout.write(
            f"{self.tag}Vuelta al listado en el producto {self.state['cursor']} "
            f"(iniciada {self.state['cycle_started'][:16]}, {len(self.state['seen'])} vistos)."
            if self.does_listing else f"{self.tag}Solo galerías (porción {self.shard + 1} de {self.shards})."
        )
        step = 0
        while not deadline or time.monotonic() < deadline:
            close_old_connections()
            step += 1
            try:
                if self.does_listing and step % opts["listing_every"] == 0:
                    self._listing_step()
                elif not self._detail_step():
                    if self.does_listing:
                        self._listing_step()
                    else:
                        time.sleep(300)   # nada en su porción por ahora
            except (DatabaseError, DropiAPIError, requests.RequestException) as exc:
                # Corte de red (PC suspendido, cambio de Wi-Fi) o Dropi caído:
                # el avance ya está guardado; se reconecta y sigue.
                self.stats["network_errors"] += 1
                self.stdout.write(
                    f"  {self.tag}{time.strftime('%H:%M')}  sin conexión ({type(exc).__name__}: "
                    f"{str(exc).strip().splitlines()[0][:120] if str(exc).strip() else '-'}): "
                    f"reintento en {NETWORK_RETRY_SECONDS} s"
                )
                connections.close_all()
                time.sleep(NETWORK_RETRY_SECONDS)
                continue
            if step % PROGRESS_EVERY == 0:
                self._progress()
        self._progress()

    def _progress(self) -> None:
        s = self.stats
        self.stdout.write(
            f"  {self.tag}{time.strftime('%H:%M')}  listado: producto {self.state['cursor']} "
            f"({s['pages']} págs, {s['listing_updated']} actualizados, {s['new']} nuevos)  |  "
            f"galerías: {s['ok']} ({s['images_before']}->{s['images_after']} fotos, {s['reactivated']} publicados)  |  "
            f"despublicados: {s['deactivated'] + s['no_existe'] + s['sin_imagenes'] + s['sin_stock']}  "
            f"errores: {s['errors']}  cortes de red: {s['network_errors']}  "
            f"ritmo {60 / max(self.limiter.interval, 0.01):.0f}/min"
        )

    # ── Detalle: galería de un producto ──────────────────────────────────────

    def _detail_step(self) -> bool:
        """False si no queda ninguna galería por traer."""
        if not self.queue:
            self.queue = [
                p for p in gallery_queue(shard=self.shard, shards=self.shards).exclude(pk__in=self.failed)[:50]
            ]
            if not self.queue:
                return False
        queued = self.queue.pop(0)
        product = Product.objects.select_related("category").filter(pk=queued.pk).first()
        if product is None:
            return True
        result = fetch_gallery(self.client, self.session, product.dropi_id, True, self.limiter)
        if result.error:
            self.stderr.write(f"  [{product.dropi_id}] {result.error}")
            self.failed.add(product.pk)
        apply_gallery_result(product, result, self.stats, reactivate=True)
        return True

    # ── Listado: una página de 40 ────────────────────────────────────────────

    def _listing_step(self) -> None:
        self.limiter.wait()
        page = _fetch_page(self.client, self.state["cursor"], PAGE_SIZE, "", self.stdout)
        if not page:
            self._finish_cycle()
            return
        self.stats["pages"] += 1

        raws = {}
        for raw in page:
            try:
                raws[int(raw.get("id") or raw.get("products_id"))] = raw
            except (TypeError, ValueError):
                continue
        existing = {p.dropi_id: p for p in Product.objects.filter(dropi_id__in=raws).select_related("category")}
        now = timezone.now()
        for dropi_id, raw in raws.items():
            product = existing.get(dropi_id)
            if product is None:
                self._create_new(raw)
                continue
            changed, events = apply_listing_raw(product, raw, deactivate_zero=True, reactivate=True)
            for event in events:
                self.stats[event] += 1
            if changed:
                if touches_page(changed):
                    product.last_synced = now
                    changed.add("last_synced")
                Product.objects.filter(pk=product.pk).update(**{f: getattr(product, f) for f in changed})
                self.stats["listing_updated"] += 1

        self.state["seen"].update(raws)
        self.state["cursor"] += len(page)
        self._save_state()

    def _create_new(self, raw: dict) -> None:
        if not self.create_new or not check_product(raw, NEW_PRODUCT_FILTERS).passed:
            return
        product, created = upsert_product(raw)
        if not created:
            return
        # Queda despublicado hasta que el detalle traiga y verifique sus fotos
        # (gallery_queue lo toma primero por no tener gallery_synced_at).
        decision = compute_price(product.cost, product.suggested_price, product.category)
        product.is_active, product.inactive_reason = False, "sin_imagenes"
        product.price, product.pricing_status = decision.price, decision.status
        product.rank_score = compute_rank_score(product)
        Product.objects.filter(pk=product.pk).update(
            is_active=False, inactive_reason="sin_imagenes", price=product.price,
            pricing_status=product.pricing_status, rank_score=product.rank_score,
        )
        self.stats["new"] += 1

    def _finish_cycle(self) -> None:
        """Fin de la vuelta: despublica los activos que Dropi ya no mostró."""
        seen = self.state["seen"]
        active_ids = set(Product.objects.filter(is_active=True).values_list("dropi_id", flat=True))
        found = len(active_ids & seen)
        if active_ids and found < 0.5 * len(active_ids):
            self.stdout.write(self.style.ERROR(
                f"  Vuelta incompleta ({found} de {len(active_ids)} activos vistos): no se despublica nada."
            ))
        else:
            missing = active_ids - seen
            n = Product.objects.filter(is_active=True, dropi_id__in=missing).update(
                is_active=False, inactive_reason="no_existe"
            )
            self.stats["deactivated"] += n
            self.stdout.write(self.style.SUCCESS(
                f"  Vuelta completa al catálogo de Dropi: {len(seen)} productos vistos, "
                f"{n} despublicados porque Dropi ya no los muestra."
            ))
        # Basura fuera de Google y duplicados con rel=canonical (incluye los
        # productos nuevos de esta vuelta). Ver services/seo_consolidation.py.
        from catalog.services.seo_consolidation import consolidate

        seo = consolidate(apply=True)
        self.stdout.write(
            f"  SEO: {seo['junk']} basura nuevos fuera de Google, "
            f"{seo['duplicates_total']} duplicados apuntando a su canónico."
        )
        self.state = self._new_cycle(self.state)
        self.state["last_cycle_finished"] = timezone.now().isoformat()
        self._save_state()
