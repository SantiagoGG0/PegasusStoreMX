"""
Genera slug para productos que lo tienen vacío (evita NoReverseMatch en tarjetas).

Usage:
    python manage.py ensure_product_slugs
"""

from django.core.management.base import BaseCommand

from catalog.models import Product


class Command(BaseCommand):
    help = "Rellena slug vacío en productos activos/inactivos"

    def handle(self, *args, **options):
        qs = Product.objects.filter(slug="")
        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No hay productos sin slug."))
            return
        for product in qs.iterator():
            product.save()
        self.stdout.write(self.style.SUCCESS(f"Slug generado para {count} producto(s)."))
