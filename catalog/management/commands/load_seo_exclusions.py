"""Sincroniza las exclusiones SEO / campañas del catálogo desde un CSV por slug.

CSV (separador ';', UTF-8): slug;exclusion;canonical_slug
  - exclusion: b, c1, c2, c3, a1, e o vacío (ver catalog.models.SEO_EXCLUSION_CHOICES)
  - canonical_slug: solo para casi duplicados; la ficha declara rel=canonical
    hacia ese producto. Se ignora si el destino no existe, no está activo o
    está excluido con noindex.

Es una sincronización: los productos que no aparecen en el archivo quedan
sin exclusión ni canónica. No desactiva productos ni cambia URLs, y usa
bulk_update para no tocar last_synced (el lastmod del sitemap).

    python manage.py load_seo_exclusions --dry-run   # solo cuenta
    python manage.py load_seo_exclusions
"""
import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import SEO_EXCLUSION_CHOICES, SEO_NOINDEX_EXCLUSIONS, Product

DEFAULT_FILE = Path(__file__).resolve().parents[2] / "data" / "seo_exclusions.csv"
VALID = {code for code, _ in SEO_EXCLUSION_CHOICES}


class Command(BaseCommand):
    help = "Carga por slug las exclusiones SEO / campañas y las canónicas de duplicados."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_FILE), help="Ruta del CSV (por defecto catalog/data/seo_exclusions.csv).")
        parser.add_argument("--dry-run", action="store_true", help="Solo cuenta lo que cambiaría; no escribe nada.")

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"No existe {path}")

        wanted: dict[str, tuple[str, str]] = {}
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for i, row in enumerate(csv.DictReader(fh, delimiter=";"), start=2):
                slug = (row.get("slug") or "").strip()
                exclusion = (row.get("exclusion") or "").strip()
                canonical = (row.get("canonical_slug") or "").strip()
                if not slug:
                    continue
                if exclusion and exclusion not in VALID:
                    raise CommandError(f"Línea {i}: exclusión desconocida {exclusion!r} para {slug}")
                wanted[slug] = (exclusion, canonical)

        products = {
            p.slug: p
            for p in Product.objects.only("id", "slug", "is_active", "seo_exclusion", "canonical_product_id")
        }
        missing = sorted(s for s in wanted if s not in products)

        # Destinos de canónica válidos: existen, activos y sin noindex propio.
        targets = {}
        for slug, (exclusion, canonical) in wanted.items():
            if canonical:
                targets.setdefault(canonical, None)
        target_problems = Counter()
        for canonical in targets:
            target = products.get(canonical)
            own_exclusion = wanted.get(canonical, ("", ""))[0]
            if target is None:
                target_problems["destino no existe"] += 1
            elif not target.is_active:
                target_problems["destino inactivo"] += 1
            elif own_exclusion in SEO_NOINDEX_EXCLUSIONS:
                target_problems["destino con noindex"] += 1
            else:
                targets[canonical] = target.pk

        stats = Counter()
        changed = []
        for slug, product in products.items():
            exclusion, canonical = wanted.get(slug, ("", ""))
            canonical_id = targets.get(canonical) if canonical else None
            if canonical_id == product.pk or exclusion in SEO_NOINDEX_EXCLUSIONS:
                # Un producto con noindex no declara canónica hacia otra ficha.
                canonical_id = None
            if exclusion:
                stats[f"exclusión {exclusion}"] += 1
            if canonical_id:
                stats["con canónica (duplicado)"] += 1
            if product.seo_exclusion != exclusion or product.canonical_product_id != canonical_id:
                product.seo_exclusion = exclusion
                product.canonical_product_id = canonical_id
                changed.append(product)

        prefix = "[dry-run] " if opts["dry_run"] else ""
        self.stdout.write(f"{prefix}Filas en el archivo: {len(wanted)} · productos en la base: {len(products)}")
        for key in sorted(stats):
            self.stdout.write(f"{prefix}  {key}: {stats[key]}")
        if missing:
            self.stdout.write(f"{prefix}  slugs del archivo que no existen: {len(missing)} (p. ej. {', '.join(missing[:5])})")
        for key, value in sorted(target_problems.items()):
            self.stdout.write(f"{prefix}  canónicas ignoradas ({key}): {value}")
        self.stdout.write(f"{prefix}Productos que cambian: {len(changed)}")

        if opts["dry_run"]:
            return
        with transaction.atomic():
            Product.objects.bulk_update(changed, ["seo_exclusion", "canonical_product"], batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"Actualizados {len(changed)} productos."))
