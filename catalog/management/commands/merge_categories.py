"""
Fusiona categorías duplicadas por nombre normalizado (strip + title).

Por cada grupo con el mismo nombre normalizado:
- Conserva la categoría con más productos.
- Reasigna todos los productos de los duplicados al conservado.
- Elimina los duplicados.

Uso:
    python manage.py merge_categories
    python manage.py merge_categories --dry-run
"""

from django.core.management.base import BaseCommand

from catalog.models import Category, Product


class Command(BaseCommand):
    help = "Fusiona categorías duplicadas normalizando nombres (sin importar mayúsculas/minúsculas)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Muestra qué se fusionaría sin modificar nada.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("-- DRY RUN: no se modificará nada --\n"))

        all_cats = list(Category.objects.all())

        # Agrupar por nombre normalizado
        groups: dict[str, list] = {}
        for cat in all_cats:
            key = cat.name.strip().title()
            groups.setdefault(key, []).append(cat)

        duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS("No hay categorías duplicadas."))
            return

        self.stdout.write(f"Grupos duplicados: {len(duplicate_groups)}\n")

        total_merged = 0
        total_reassigned = 0

        for normalized_name, cats in sorted(duplicate_groups.items()):
            # Contar productos por categoría
            counts = {cat.id: Product.objects.filter(category=cat).count() for cat in cats}

            # Conservar la que tiene más productos (desempate: menor id = más antigua)
            keeper = max(cats, key=lambda c: (counts[c.id], -c.id))
            # Normalizar el nombre del keeper
            keeper_name = normalized_name

            duplicates = [c for c in cats if c.id != keeper.id]
            dup_count = sum(counts[d.id] for d in duplicates)

            self.stdout.write(
                f"\n[{normalized_name}] {len(cats)} entradas → conservar: '{keeper.name}' "
                f"(id={keeper.id}, {counts[keeper.id]} productos)"
            )
            for d in duplicates:
                self.stdout.write(
                    f"  FUSIONAR '{d.name}' (id={d.id}, {counts[d.id]} productos) → '{keeper_name}'"
                )

            if not dry_run:
                # Renombrar keeper al nombre normalizado
                if keeper.name != keeper_name:
                    keeper.name = keeper_name
                    keeper.save(update_fields=["name"])

                # Reasignar productos
                for dup in duplicates:
                    reassigned = Product.objects.filter(category=dup).update(category=keeper)
                    total_reassigned += reassigned

                # Eliminar duplicados
                dup_ids = [d.id for d in duplicates]
                Category.objects.filter(id__in=dup_ids).delete()
                total_merged += len(duplicates)

        if dry_run:
            est_merged = sum(len(v) - 1 for v in duplicate_groups.values())
            self.stdout.write(
                self.style.WARNING(f"\nSe fusionarían {est_merged} categorías duplicadas.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nFusionadas {total_merged} categorías duplicadas. "
                    f"Reasignados {total_reassigned} productos."
                )
            )
