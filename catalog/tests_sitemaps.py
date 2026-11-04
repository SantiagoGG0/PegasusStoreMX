from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from .models import Category, Product


class SitemapIndexTests(TestCase):
    """Índice /sitemap.xml con secciones por tipo, lastmod real y caché."""

    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        self.old = self._product(1, "crema-vieja")
        self.new = self._product(2, "crema-nueva")
        self.hidden = self._product(3, "parche-adelgazante", seo_exclusion="c1")
        self.newest = timezone.now() - timedelta(days=1)
        Product.objects.filter(pk=self.old.pk).update(last_synced=timezone.now() - timedelta(days=30))
        Product.objects.filter(pk=self.new.pk).update(last_synced=self.newest)
        # El excluido es el más reciente: no debe marcar el lastmod.
        Product.objects.filter(pk=self.hidden.pk).update(last_synced=timezone.now())

    def _product(self, dropi_id, slug, **kwargs):
        return Product.objects.create(
            dropi_id=dropi_id, name=slug, slug=slug, category=self.cat, price=Decimal("30000"),
            cost=Decimal("10000"), stock=5, is_active=True, **kwargs,
        )

    def test_index_lists_three_sections_with_lastmod(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        for section in ("productos", "categorias", "paginas"):
            self.assertIn(f"/sitemap-{section}.xml</loc>", xml)
        self.assertEqual(xml.count("<lastmod>"), 3)
        self.assertIn(self.newest.astimezone(timezone.get_current_timezone()).date().isoformat(), xml)

    def test_products_section_has_real_lastmod_per_url(self):
        xml = self.client.get("/sitemap-productos.xml").content.decode()
        self.assertEqual(xml.count("<url>"), 2)
        self.assertEqual(xml.count("<lastmod>"), 2)
        self.assertNotIn("parche-adelgazante", xml)

    def test_categories_lastmod_from_indexable_products(self):
        xml = self.client.get("/sitemap-categorias.xml").content.decode()
        self.assertIn("/categoria/belleza/", xml)
        self.assertIn(f"<lastmod>{self.newest.astimezone(timezone.get_current_timezone()).date().isoformat()}", xml)

    def test_static_pages_only_home_declares_lastmod(self):
        xml = self.client.get("/sitemap-paginas.xml").content.decode()
        self.assertEqual(xml.count("<url>"), 8)  # + Quiénes somos
        self.assertEqual(xml.count("<lastmod>"), 1)

    def test_second_request_is_served_from_cache(self):
        self.client.get("/sitemap-productos.xml")
        with self.assertNumQueries(0):
            response = self.client.get("/sitemap-productos.xml")
        self.assertEqual(response.status_code, 200)

    def test_unknown_section_404(self):
        self.assertEqual(self.client.get("/sitemap-otra.xml").status_code, 404)
