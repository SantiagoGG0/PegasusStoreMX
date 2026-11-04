import json
import re
from decimal import Decimal

from django.test import TestCase, override_settings

from catalog.models import Category, Product

CANONICAL = "https://www.pegasusstoreco.com"


@override_settings(
    STORE_SITE_URL=CANONICAL,
    LEGACY_HOSTS=[],  # sin redirección: se prueba el host que ve cada URL
    ALLOWED_HOSTS=["testserver"],
)
class CanonicalUrlTests(TestCase):
    """Canonical, og:url, JSON-LD, sitemap y robots usan STORE_SITE_URL aunque
    la petición llegue por otro host (antes se autocanonizaba cada host)."""

    def setUp(self):
        cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        self.product = Product.objects.create(
            dropi_id=1, name="Crema", slug="crema", category=cat,
            price=Decimal("30000"), cost=Decimal("10000"), stock=5, is_active=True,
        )

    def test_home_canonical_and_og_url(self):
        html = self.client.get("/").content.decode()
        self.assertIn(f'<link rel="canonical" href="{CANONICAL}/">', html)
        self.assertIn(f'<meta property="og:url" content="{CANONICAL}/">', html)
        self.assertNotIn("http://testserver", html)

    def test_product_canonical_and_json_ld(self):
        html = self.client.get("/producto/crema/").content.decode()
        self.assertIn(f'<link rel="canonical" href="{CANONICAL}/producto/crema/">', html)
        graph = json.loads(re.search(r'(?s)<script type="application/ld\+json">(.*?)</script>', html).group(1))
        ld = next(node for node in graph["@graph"] if node["@type"] == "Product")
        self.assertEqual(ld["url"], f"{CANONICAL}/producto/crema/")
        self.assertEqual(ld["offers"]["url"], f"{CANONICAL}/producto/crema/")

    def test_sitemap_uses_canonical_host(self):
        from django.core.cache import cache

        cache.clear()
        index = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(f"<loc>{CANONICAL}/sitemap-productos.xml</loc>", index)
        self.assertNotIn("testserver", index)
        xml = self.client.get("/sitemap-productos.xml").content.decode()
        self.assertIn(f"<loc>{CANONICAL}/producto/crema/</loc>", xml)
        self.assertNotIn("testserver", xml)

    def test_robots_sitemap_line(self):
        txt = self.client.get("/robots.txt").content.decode()
        self.assertIn(f"Sitemap: {CANONICAL}/sitemap.xml", txt)

    @override_settings(STORE_SITE_URL="")
    def test_falls_back_to_request_host_in_development(self):
        html = self.client.get("/").content.decode()
        self.assertIn('<link rel="canonical" href="http://testserver/">', html)
