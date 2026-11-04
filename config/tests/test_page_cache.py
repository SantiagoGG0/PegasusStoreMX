"""Caché de páginas para visitantes sin sesión (AnonymousPageCacheMiddleware)."""
from decimal import Decimal

from django.conf import settings
from django.core.cache import caches
from django.test import TestCase, override_settings

from catalog.models import Category, Product


@override_settings(PAGE_CACHE_SECONDS=300)
class AnonymousPageCacheTests(TestCase):
    def setUp(self):
        caches["pages"].clear()
        caches["default"].clear()
        cat = Category.objects.create(dropi_id="store:hogar", name="Hogar")
        self.product = Product.objects.create(
            dropi_id=1, name="Organizador", slug="organizador", category=cat,
            price=Decimal("59900"), cost=Decimal("20000"), stock=10, is_active=True,
            images=["https://x/1.jpg", "https://x/2.jpg"],
        )

    def test_second_anonymous_visit_is_served_from_cache(self):
        first = self.client.get("/producto/organizador/")
        self.assertEqual(first["X-Page-Cache"], "MISS")
        self.assertFalse(first.cookies, "la ficha no debe poner cookies (se sirve desde caché)")
        second = self.client.get("/producto/organizador/")
        self.assertEqual(second["X-Page-Cache"], "HIT")
        self.assertEqual(second.content, first.content)
        self.assertEqual(second["X-Frame-Options"], first["X-Frame-Options"])

    def test_home_and_category_set_no_cookies(self):
        for url in ("/", "/categoria/hogar/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.cookies, url)
            self.assertEqual(response["X-Page-Cache"], "MISS")

    def test_visitor_with_session_is_never_served_from_cache(self):
        self.client.get("/producto/organizador/")  # queda en caché
        session = self.client.session
        session["visitor_city"] = {"city": "Medellín", "state": "Antioquia"}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
        response = self.client.get("/producto/organizador/")
        self.assertNotIn("X-Page-Cache", response)
        self.assertIn('value="Medellín"', response.content.decode())

    def test_cart_and_checkout_are_not_cached(self):
        for url in ("/carrito/", "/pedidos/checkout/"):
            response = self.client.get(url)
            self.assertNotIn("X-Page-Cache", response, url)

    def test_pdp_form_has_no_server_token_and_cart_state_gives_cookie(self):
        html = self.client.get("/producto/organizador/").content.decode()
        self.assertIn('name="csrfmiddlewaretoken" value="" data-csrf', html)
        state = self.client.get("/carrito/estado/")
        self.assertIn(settings.CSRF_COOKIE_NAME, state.cookies)
