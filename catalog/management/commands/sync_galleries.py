"""
Management command: sync_galleries

Trae la galería completa de cada producto desde el detalle de Dropi
(products/v2/{id}) — el listado solo trae 1 foto — y verifica que cada imagen
exista en el CDN. Aprovecha el mismo request para refrescar stock, costo y
precio sugerido, y recalcula precio y puntaje de relevancia.

Despublica (is_active=False + inactive_reason, nunca borra):
  - no_existe     : Dropi ya no devuelve el producto.
  - sin_imagenes  : ninguna imagen válida.
  - sin_stock     : stock 0 en el detalle.
Y republica los que había despublicado un sync automático cuando el motivo
desaparece (con --reactivate).

Es reanudable: procesa primero los que nunca se sincronizaron y luego los más
viejos (gallery_synced_at), en el orden de prioridad de categorías. La
sincronización continua (`catalog_worker`) usa la misma lógica.

Usage:
    python manage.py sync_galleries --dry-run --limit 50
    python manage.py sync_galleries --category belleza --limit 2000
    python manage.py sync_galleries --reactivate --max-minutes 60
"""
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.core.management.base import BaseCommand

from catalog.services.gallery_sync import RateLimiter, apply_gallery_result, fetch_gallery, gallery_queue
from dropi_client import DropiClient


class Command(BaseCommand):
    help = "Galería completa + stock/costo desde el detalle de Dropi; despublica productos sin imágenes válidas o sin stock."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Máximo de productos a procesar (0 = todos).")
        parser.add_argument("--workers", type=int, default=2, help="Hilos en paralelo (la verificación de imágenes no cuenta para el límite de Dropi). Default: 2")
        parser.add_argument("--rps", type=float, default=0.1, help="Máximo de requests por segundo a Dropi. Default: 0.1 (1 cada 10 s; Dropi bloquea con 1 cada 6 s)")
        parser.add_argument("--max-minutes", type=float, default=0, help="Corta limpio tras N minutos; la siguiente corrida retoma (0 = sin límite).")
        parser.add_argument("--stale-days", type=int, default=30, help="Re-sincroniza galerías más viejas que N días. Default: 30")
        parser.add_argument("--category", default="", help="Solo esta categoría (ej. belleza, tecnologia).")
        parser.add_argument("--include-inactive", action="store_true", help="Incluye productos despublicados automáticamente (para --reactivate).")
        parser.add_argument("--reactivate", action="store_true", help="Republica productos despublicados automáticamente si ya cumplen.")
        parser.add_argument("--no-verify", action="store_true", help="No verifica que cada imagen exista en el CDN.")
        parser.add_argument("--no-reprice", action="store_true", help="No recalcula el precio si cambia el costo.")
        parser.add_argument("--dry-run", action="store_true", help="No escribe en la DB, solo reporta.")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        qs = gallery_queue(
            stale_days=opts["stale_days"],
            include_inactive=opts["include_inactive"] or opts["reactivate"],
            category=opts["category"],
        )
        products = list(qs[: opts["limit"]] if opts["limit"] else qs)
        total = len(products)
        self.stdout.write(f"{total} productos por sincronizar (workers={opts['workers']}{', DRY RUN' if dry_run else ''}).")
        if not total:
            return

        local = threading.local()
        limiter = RateLimiter(opts["rps"])
        deadline = time.monotonic() + opts["max_minutes"] * 60 if opts["max_minutes"] else None

        def fetch(dropi_id):
            if deadline and time.monotonic() > deadline:
                return None
            if not hasattr(local, "client"):
                local.client, local.session = DropiClient(), requests.Session()
            return fetch_gallery(local.client, local.session, dropi_id, not opts["no_verify"], limiter)

        by_dropi = {p.dropi_id: p for p in products}
        stats = Counter()
        started = time.monotonic()

        with ThreadPoolExecutor(max_workers=opts["workers"]) as pool:
            futures = [pool.submit(fetch, did) for did in by_dropi]
            for done, future in enumerate(as_completed(futures), 1):
                result = future.result()
                if result is None:
                    stats["timed_out"] += 1
                    continue
                if result.error:
                    self.stderr.write(f"  [{result.dropi_id}] {result.error}")
                apply_gallery_result(
                    by_dropi[result.dropi_id], result, stats,
                    reactivate=opts["reactivate"], reprice=not opts["no_reprice"], save=not dry_run,
                )
                if done % 25 == 0 or done == total:
                    rate = done / max(time.monotonic() - started, 1)
                    self.stdout.write(
                        f"  {done}/{total}  ({rate:.1f}/s, ~{(total - done) / rate / 60:.0f} min restantes)  "
                        f"imgs {stats['images_before']}->{stats['images_after']}  rotas={stats['broken']}  "
                        f"despublicados={stats['no_existe'] + stats['sin_imagenes'] + stats['sin_stock']}  errores={stats['errors']}  "
                        f"ritmo Dropi={60 / max(limiter.interval, 0.01):.0f}/min"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"\n{'[DRY RUN] ' if dry_run else ''}Listo: {stats['ok']} sincronizados, "
            f"{stats['more_images']} ganaron imágenes ({stats['images_before']} -> {stats['images_after']} en total), "
            f"{stats['broken']} imágenes rotas descartadas.\n"
            f"  Despublicados: {stats['no_existe']} ya no existen, {stats['sin_imagenes']} sin imágenes válidas, "
            f"{stats['sin_stock']} sin stock.  Republicados: {stats['reactivated']}.  "
            f"Precio recalculado: {stats['repriced']}.  Errores de API: {stats['errors']}."
            + (f"\n  Quedaron {stats['timed_out']} para la próxima corrida (--max-minutes)." if stats["timed_out"] else "")
        ))
