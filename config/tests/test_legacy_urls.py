from django.test import TestCase


class LegacyUrlRedirectTests(TestCase):
    """URLs retiradas en el rediseño 2026: 301 en vez de 404."""

    def test_account_urls_redirect_home(self):
        for path in ("/cuenta/", "/cuenta", "/cuenta/entrar/", "/cuenta/recuperar-clave/enviado/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 301, path)
            self.assertEqual(response["Location"], "/", path)

    def test_my_orders_and_magic_links_redirect_to_tracking(self):
        for path in ("/pedidos/mis-pedidos/", "/pedidos/acceso/abc123:token/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 301, path)
            self.assertEqual(response["Location"], "/pedidos/seguimiento/", path)

    def test_tracking_page_still_works(self):
        self.assertEqual(self.client.get("/pedidos/seguimiento/").status_code, 200)


class RobotsTxtTests(TestCase):
    def test_tracking_allowed_while_rest_of_orders_blocked(self):
        # /pedidos/seguimiento/ está en el sitemap: robots no puede bloquearla.
        lines = self.client.get("/robots.txt").content.decode().splitlines()
        self.assertIn("Disallow: /pedidos/", lines)
        self.assertIn("Allow: /pedidos/seguimiento/", lines)

    def test_tracking_page_is_in_sitemap(self):
        from django.core.cache import cache

        cache.clear()
        self.assertIn("/pedidos/seguimiento/</loc>", self.client.get("/sitemap-paginas.xml").content.decode())
