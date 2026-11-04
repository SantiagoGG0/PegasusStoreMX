"""Colecciones por tipo de producto (/categoria/x/y/)."""
import json
import re
from decimal import Decimal
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from catalog.models import Category, Collection, Product
from catalog.services.collections import compile_matcher, refresh_collections


class MatcherTests(SimpleTestCase):
    def test_whole_words_accents_and_plurals(self):
        m = compile_matcher("organizador cocina\nespeciero", "maquillaje")
        self.assertTrue(m("Organizador Cocina Giratorio"))
        self.assertTrue(m("Organizadores Cocina x3"))  # plural
        self.assertTrue(m("Especieros magnéticos"))
        self.assertFalse(m("Organizador de maquillaje cocina"))  # excluido
        self.assertFalse(m("Reorganizador cocinado"))  # no son palabras completas

    def test_accented_terms_match_unaccented_names(self):
        m = compile_matcher("lampara solar")
        self.assertTrue(m("LÁMPARA SOLAR 300W"))
        self.assertFalse(m("Lámpara de mesa"))


class CollectionPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(dropi_id="store:cocina", name="Cocina")
        base = dict(category=self.cat, cost=Decimal("10000"), price=Decimal("45000"), stock=10, is_active=True,
                    images=["https://x/1.jpg", "https://x/2.jpg"])
        self.p1 = Product.objects.create(dropi_id=1, name="Organizador de cocina giratorio", slug="org-cocina", **base)
        Product.objects.create(dropi_id=2, name="Especiero magnético", slug="especiero", **base)
        Product.objects.create(dropi_id=3, name="Sartén antiadherente", slug="sarten", **base)
        Product.objects.create(dropi_id=4, name="Organizador de cocina excluido", slug="excluido", seo_exclusion="b", **base)
        self.coll = Collection.objects.create(
            category=self.cat, slug="organizadores-de-cocina", name="Organizadores de cocina",
            include_terms="organizador cocina\norganizador de cocina\nespeciero",
            intro="Primer párrafo.\n\nSegundo párrafo con consejos.",
            faq=[{"q": "¿Pregunta?", "a": "Respuesta."}], is_published=True,
        )
        refresh_collections()

    def test_refresh_counts_only_listable_products(self):
        self.coll.refresh_from_db()
        self.assertEqual(self.coll.product_count, 2)

    def test_page_renders_with_seo_and_faq(self):
        response = self.client.get("/categoria/cocina/organizadores-de-cocina/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("<h1", html)
        self.assertIn("Organizadores de cocina", html)
        self.assertIn("Segundo párrafo con consejos.", html)
        self.assertNotIn("Sartén", html)
        self.assertIn('<link rel="canonical" href="', html)
        graph = json.loads(re.search(r'(?s)<script type="application/ld\+json">(.*?)</script>', html).group(1))["@graph"]
        self.assertEqual({n["@type"] for n in graph}, {"CollectionPage", "BreadcrumbList", "FAQPage"})

    def test_unpublished_is_404_and_category_page_unchanged_otherwise(self):
        self.coll.is_published = False
        self.coll.save()
        self.assertEqual(self.client.get("/categoria/cocina/organizadores-de-cocina/").status_code, 404)
        self.assertNotContains(self.client.get("/categoria/cocina/"), "Explora por tipo")

    def test_category_and_product_link_to_collection(self):
        self.assertContains(self.client.get("/categoria/cocina/"), 'href="/categoria/cocina/organizadores-de-cocina/"')
        self.assertContains(self.client.get("/producto/org-cocina/"), 'href="/categoria/cocina/organizadores-de-cocina/"')

    def test_sitemap_lists_collection(self):
        xml = self.client.get("/sitemap-colecciones.xml").content.decode()
        self.assertIn("/categoria/cocina/organizadores-de-cocina/", xml)

    def test_out_of_range_page_is_404(self):
        self.assertEqual(self.client.get("/categoria/cocina/organizadores-de-cocina/?page=9").status_code, 404)


class SeedCommandTests(TestCase):
    def test_load_seed_creates_drafts_when_too_few_products(self):
        from catalog.data.collections_seed import SEED
        from catalog.services.categorization import store_category_dropi_id

        for key in {item["category"] for item in SEED}:
            Category.objects.create(dropi_id=store_category_dropi_id(key), name=key)
        call_command("refresh_collections", "--load-seed", stdout=StringIO())
        self.assertEqual(Collection.objects.count(), len(SEED))
        self.assertFalse(Collection.objects.filter(is_published=True).exists())  # catálogo vacío: todas en borrador
        # Los textos de la semilla no se repiten entre colecciones.
        intros = list(Collection.objects.values_list("intro", flat=True))
        self.assertEqual(len(intros), len(set(intros)))
