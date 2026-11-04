"""
Management command: backfill_product_images

Uses Gemini (catalog.services.image_generation) to fill the gallery of
products that have too few images:
  - 0 images : generate one from name/description (text-to-image).
  - 1 image  : generate an extra variation using the existing image as
               reference (image-to-image), so the gallery has more than one photo.

Results are saved as `ProductImage` rows (custom images) — the original
Dropi `images` JSON is never touched, so this is fully reversible (just
delete the generated ProductImage rows).

Only touches products that are currently sellable (is_active=True, stock>0,
image_flagged=False). Products with 0 images that fail to generate reliably
are flagged with image_flagged=True for manual review instead of guessing.

Usage:
    python manage.py backfill_product_images --dry-run --limit 50
    python manage.py backfill_product_images --only zero --limit 200
    python manage.py backfill_product_images --only one
"""
import json
import logging
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Product
from catalog.services.image_generation import ensure_product_image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Genera imágenes faltantes de productos con Gemini (0 o 1 imagen)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=["zero", "one", "both"],
            default="both",
            help="Qué grupo de productos procesar. Default: both.",
        )
        parser.add_argument("--limit", type=int, default=0, help="Máximo de productos a procesar. 0 = sin límite.")
        parser.add_argument("--dry-run", action="store_true", help="No genera ni guarda nada, solo cuenta candidatos.")
        parser.add_argument("--delay", type=float, default=1.0, metavar="SECS", help="Pausa entre llamadas a Gemini.")
        parser.add_argument(
            "--backup-file",
            type=str,
            default="",
            help="Ruta JSONL donde registrar el estado previo de cada producto tocado.",
        )

    def handle(self, *args, **options):
        only = options["only"]
        limit = options["limit"]
        dry_run = options["dry_run"]
        delay = options["delay"]
        backup_file = options["backup_file"] or (
            f"backups/images-before-backfill-{timezone.now():%Y%m%d-%H%M}.jsonl"
        )

        qs = (
            Product.objects.filter(is_active=True, stock__gt=0, image_flagged=False)
            .prefetch_related("custom_images")
            .order_by("pk")
        )

        zero_candidates = []
        one_candidates = []
        for product in qs.iterator(chunk_size=500):
            if product.custom_images.all():
                continue  # already has custom/generated images
            image_count = len(product.images or [])
            if image_count == 0:
                zero_candidates.append(product)
            elif image_count == 1:
                one_candidates.append(product)

        targets = []
        if only in ("zero", "both"):
            targets += [("zero", p) for p in zero_candidates]
        if only in ("one", "both"):
            targets += [("one", p) for p in one_candidates]
        if limit:
            targets = targets[:limit]

        self.stdout.write(
            f"Candidatos: {len(zero_candidates)} sin imagen, {len(one_candidates)} con 1 imagen. "
            f"Procesando {len(targets)}."
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY RUN] no se genera ni guarda nada."))
            return

        backup_path = Path(backup_file)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_handle = backup_path.open("w", encoding="utf-8")

        generated = 0
        flagged = 0
        errors = 0

        try:
            for kind, product in targets:
                backup_handle.write(json.dumps({
                    "id": product.pk,
                    "dropi_id": product.dropi_id,
                    "name": product.name,
                    "images": product.images,
                }, ensure_ascii=False) + "\n")

                status = ensure_product_image(product)
                if status == "generated":
                    generated += 1
                    self.stdout.write(f"  + [{product.pk}] {product.name[:50]} ({kind})")
                elif status == "flagged":
                    flagged += 1
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"  ERROR [{product.pk}] {product.name[:50]}: marcado para revisión"))
                elif status == "error":
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"  ERROR [{product.pk}] {product.name[:50]}: generación falló"))
                time.sleep(delay)
        finally:
            backup_handle.close()

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Generadas: {generated}  Marcadas para revisión: {flagged}  Errores: {errors}"
        ))
        self.stdout.write(f"Backup: {backup_path}")
