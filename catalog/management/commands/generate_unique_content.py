"""
Management command: generate_unique_content

Genera meta_title, meta_description y description_unique por PLANTILLAS +
slot-filling determinista (catalog.services.content_generation) — sin IA,
sin llamadas a servicios externos. Ver ese módulo para la fórmula completa
y sus límites honestos (reduce duplicado, no lo elimina al 100%).

Alcance por defecto: productos activos y rentables (is_active=True +
Product.is_profitable), excluyendo nombres basura/rotos
(has_usable_name). No se generó contenido para productos needs_combo ni
para el resto de "sin margen" — ese catálogo puede desactivarse más
adelante, generar contenido sobre él sería trabajo desperdiciado.

Nunca sobrescribe contenido ya generado a menos que se pase --force
(así se puede correr en fases sin perder ediciones manuales del admin).

Usage:
    python manage.py generate_unique_content --dry-run
    python manage.py generate_unique_content --limit 50
    python manage.py generate_unique_content
    python manage.py generate_unique_content --force   # regenera incluso lo ya poblado
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Product
from catalog.services.content_generation import generate_unique_content, has_usable_name

BULK_UPDATE_BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Genera meta_title/meta_description/description_unique por plantillas (sin IA) para el catálogo activo y rentable."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Máximo de productos a procesar. 0 = sin límite.")
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo cuenta candidatos.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenera incluso productos que ya tienen meta_description poblado (pisa ediciones manuales).",
        )
        parser.add_argument(
            "--backup-file",
            type=str,
            default="",
            help="Ruta JSONL donde registrar el estado previo de cada producto tocado.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        dry_run = options["dry_run"]
        force = options["force"]
        backup_file = options["backup_file"] or (
            f"backups/content-before-generate-{timezone.now():%Y%m%d-%H%M}.jsonl"
        )

        qs = Product.objects.filter(is_active=True).select_related("category").order_by("pk")

        skipped_needs_combo = 0
        skipped_unprofitable = 0
        skipped_bad_name = 0
        skipped_already_done = 0
        targets = []

        for product in qs.iterator(chunk_size=500):
            if product.needs_combo:
                skipped_needs_combo += 1
                continue
            if not product.is_profitable:
                skipped_unprofitable += 1
                continue
            if not has_usable_name(product.name):
                skipped_bad_name += 1
                continue
            if not force and product.meta_description:
                skipped_already_done += 1
                continue
            targets.append(product)

        if limit:
            targets = targets[:limit]

        self.stdout.write(
            f"Candidatos a generar: {len(targets)}\n"
            f"  Omitidos por needs_combo:        {skipped_needs_combo}\n"
            f"  Omitidos por sin margen:         {skipped_unprofitable}\n"
            f"  Omitidos por nombre roto/basura: {skipped_bad_name}\n"
            f"  Omitidos por ya generados:       {skipped_already_done}"
            + (" (usa --force para regenerar)" if skipped_already_done else "")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] no se generó ni guardó nada."))
            return

        if not targets:
            self.stdout.write(self.style.WARNING("\nNada que generar."))
            return

        backup_path = Path(backup_file)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        generated = 0
        to_update = []
        with backup_path.open("w", encoding="utf-8") as backup_handle:
            for product in targets:
                backup_handle.write(json.dumps({
                    "id": product.pk,
                    "dropi_id": product.dropi_id,
                    "name": product.name,
                    "meta_title": product.meta_title,
                    "meta_description": product.meta_description,
                    "description_unique": product.description_unique,
                }, ensure_ascii=False) + "\n")

                content = generate_unique_content(product)
                product.meta_title = content["meta_title"]
                product.meta_description = content["meta_description"]
                product.description_unique = content["description_unique"]
                to_update.append(product)
                generated += 1

        for i in range(0, len(to_update), BULK_UPDATE_BATCH_SIZE):
            Product.objects.bulk_update(
                to_update[i:i + BULK_UPDATE_BATCH_SIZE],
                ["meta_title", "meta_description", "description_unique"],
            )

        self.stdout.write(self.style.SUCCESS(f"\n✓ {generated} producto(s) actualizados."))
        self.stdout.write(f"Backup: {backup_path}")
