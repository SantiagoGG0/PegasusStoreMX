from django.test import TestCase, override_settings


@override_settings(ALLOWED_HOSTS=["monkfish-app-6bpr3.ondigitalocean.app", "www.pegasusstoremx.com"])
class PreviewHostNoindexTests(TestCase):
    PREVIEW = "monkfish-app-6bpr3.ondigitalocean.app"
    REAL = "www.pegasusstoremx.com"

    def test_preview_host_is_closed_to_search_engines(self):
        robots = self.client.get("/robots.txt", HTTP_HOST=self.PREVIEW).content.decode()
        self.assertEqual(robots.strip(), "User-agent: *\nDisallow: /")
        page = self.client.get("/legal/terminos/", HTTP_HOST=self.PREVIEW)
        self.assertEqual(page["X-Robots-Tag"], "noindex, nofollow")

    def test_real_domain_stays_open(self):
        robots = self.client.get("/robots.txt", HTTP_HOST=self.REAL).content.decode()
        self.assertIn("Allow: /", robots)
        self.assertIn("Sitemap:", robots)
        page = self.client.get("/legal/terminos/", HTTP_HOST=self.REAL)
        self.assertFalse(page.has_header("X-Robots-Tag"))

    def test_cached_page_does_not_carry_noindex_to_the_real_domain(self):
        # La caché de páginas no distingue hosts: la cabecera se calcula afuera.
        self.client.get("/legal/terminos/", HTTP_HOST=self.PREVIEW)
        page = self.client.get("/legal/terminos/", HTTP_HOST=self.REAL)
        self.assertFalse(page.has_header("X-Robots-Tag"))
