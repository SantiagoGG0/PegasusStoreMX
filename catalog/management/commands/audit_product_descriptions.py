from collections import Counter
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Product
from catalog.services.description_sanitizer import (
    find_description_issues,
    sanitize_product_description,
)


class Command(BaseCommand):
    help = "Audita y limpia descripciones de productos importadas desde proveedores."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Guarda la descripcion sanitizada.")
        parser.add_argument("--limit", type=int, default=0, help="Maximo de productos a escanear.")
        parser.add_argument("--start-id", type=int, default=0, help="Escanea desde este ID interno.")
        parser.add_argument("--end-id", type=int, default=0, help="Escanea hasta este ID interno.")
        parser.add_argument("--batch-size", type=int, default=1000, help="Tamano de lote DB.")
        parser.add_argument("--summary-only", action="store_true", help="Imprime solo totales.")
        parser.add_argument(
            "--backup-file",
            type=str,
            default="",
            help="Ruta JSONL donde guardar descripciones originales antes de --fix.",
        )
        parser.add_argument(
            "--restore",
            type=str,
            default="",
            help="Restaura descripciones desde un backup JSONL generado por este comando.",
        )

    def handle(self, *args, **options):
        if options["restore"]:
            self._restore_descriptions(Path(options["restore"]), options["batch_size"])
            return

        fix = options["fix"]
        limit = options["limit"]
        start_id = options["start_id"]
        end_id = options["end_id"]
        batch_size = options["batch_size"]
        summary_only = options["summary_only"]
        backup_file = options["backup_file"]
        backup_handle = None

        if backup_file:
            backup_path = Path(backup_file)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_handle = backup_path.open("w", encoding="utf-8")

        qs = Product.objects.only("id", "dropi_id", "name", "description").order_by("id")
        if start_id:
            qs = qs.filter(pk__gte=start_id)
        if end_id:
            qs = qs.filter(pk__lte=end_id)

        scanned = 0
        affected = 0
        updated = 0
        issue_counts: Counter[str] = Counter()
        last_pk = start_id - 1 if start_id else 0

        try:
            while True:
                remaining = limit - scanned if limit else batch_size
                if remaining <= 0:
                    break
                current_batch_size = min(batch_size, remaining)
                batch = list(qs.filter(pk__gt=last_pk)[:current_batch_size])
                if not batch:
                    break

                updates = []
                for product in batch:
                    last_pk = product.pk
                    scanned += 1

                    issues = find_description_issues(product.description)
                    if not issues:
                        continue

                    affected += 1
                    issue_counts.update(issues)
                    cleaned = sanitize_product_description(product.description)

                    if not summary_only:
                        self.stdout.write(
                            f"{product.pk} [{product.dropi_id}] {product.name[:80]}: "
                            f"{', '.join(issues)}"
                        )

                    if fix and cleaned != product.description:
                        if backup_handle:
                            backup_handle.write(
                                json.dumps(
                                    {
                                        "id": product.pk,
                                        "dropi_id": product.dropi_id,
                                        "name": product.name,
                                        "description": product.description,
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                        product.description = cleaned
                        updates.append(product)

                if updates:
                    Product.objects.bulk_update(updates, ["description"], batch_size=batch_size)
                    updated += len(updates)

                if limit and scanned >= limit:
                    break
        finally:
            if backup_handle:
                backup_handle.close()

        self.stdout.write(f"Escaneados: {scanned}")
        self.stdout.write(f"Afectados: {affected}")
        if fix:
            self.stdout.write(f"Actualizados: {updated}")
            if backup_file:
                self.stdout.write(f"Backup: {backup_file}")
        for issue_id, count in issue_counts.most_common():
            self.stdout.write(f"{issue_id}: {count}")

    def _restore_descriptions(self, backup_path: Path, batch_size: int):
        if not backup_path.exists():
            raise CommandError(f"Backup no existe: {backup_path}")

        restored = 0
        skipped = 0
        updates = []

        with backup_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CommandError(f"JSON invalido en linea {line_number}: {exc}") from exc

                product = Product.objects.filter(pk=record.get("id")).only("id", "dropi_id", "description").first()
                if not product or product.dropi_id != record.get("dropi_id"):
                    skipped += 1
                    continue

                product.description = record.get("description") or ""
                updates.append(product)
                restored += 1

                if len(updates) >= batch_size:
                    Product.objects.bulk_update(updates, ["description"], batch_size=batch_size)
                    updates.clear()

        if updates:
            Product.objects.bulk_update(updates, ["description"], batch_size=batch_size)

        self.stdout.write(f"Restaurados: {restored}")
        self.stdout.write(f"Omitidos: {skipped}")
