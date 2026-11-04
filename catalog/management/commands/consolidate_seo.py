"""
Management command: consolidate_seo

Marca productos basura (seo_exclusion="b") y une duplicados por nombre con
rel=canonical hacia el mejor de cada grupo. Ver
catalog/services/seo_consolidation.py. Simulación por defecto.

Usage:
    python manage.py consolidate_seo
    python manage.py consolidate_seo --apply
"""
from django.core.management.base import BaseCommand

from catalog.services.seo_consolidation import consolidate


class Command(BaseCommand):
    help = "Basura fuera de Google y duplicados con rel=canonical al mejor de cada grupo. Simulación por defecto."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe los cambios.")

    def handle(self, *args, **opts):
        s = consolidate(apply=opts["apply"])
        self.stdout.write(
            f"Basura marcada (fuera de Google/listas/campañas): {s['junk']}\n"
            f"Grupos de nombres repetidos: {s['groups']} → duplicados que apuntan a su canónico: {s['duplicates_total']}\n"
            f"Cambios de canonical: {s['canonicalized']} nuevos, {s['uncanonicalized']} quitados"
        )
        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("Simulación: no se cambió nada. Usa --apply."))
        else:
            self.stdout.write(self.style.SUCCESS("OK: aplicado."))
