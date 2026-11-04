from decimal import Decimal

from django.test import TestCase

from .models import Category, Product


class UnavailableProductTests(TestCase):
    """Un producto desactivado ya no da 404: página "agotado" (200, noindex)
    con hasta 4 alternativas disponibles de la misma categoría."""

    def setUp(self):
        self.cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        other = Category.objects.create(dropi_id="store:hogar", name="Hogar")
        self.gone = self._product(1, "crema-retirada", self.cat, is_active=False)
        for i in range(2, 8):  # 6 alternativas válidas: solo se muestran 4
            self._product(i, f"alt-{i}", self.cat)
        self._product(20, "sin-stock", self.cat, stock=0)
        self._product(21, "inactiva", self.cat, is_active=False)
        self._product(22, "otra-categoria", other)

    def _product(self, dropi_id, slug, category, is_active=True, stock=5):
        return Product.objects.create(
            dropi_id=dropi_id, name=slug.replace("-", " "), slug=slug, category=category,
            price=Decimal("30000"), cost=Decimal("10000"), stock=stock, is_active=is_active,
        )

    def test_inactive_product_shows_unavailable_page(self):
        response = self.client.get("/producto/crema-retirada/")
        self.assertEqual(response.status_code, 410)  # retirado: Google lo saca sin "soft 404"
        self.assertTemplateUsed(response, "catalog/unavailable.html")
        html = response.content.decode()
        self.assertIn('<meta name="robots" content="noindex,follow">', html)
        self.assertIn("ya no está disponible", html)
        self.assertNotIn('"@type": "Product"', html)  # sin JSON-LD de producto

    def test_shows_four_available_alternatives_from_same_category(self):
        alternatives = self.client.get("/producto/crema-retirada/").context["alternatives"]
        self.assertEqual(len(alternatives), 4)
        for p in alternatives:
            self.assertEqual(p.category_id, self.cat.pk)
            self.assertTrue(p.is_active)
            self.assertGreater(p.stock, 0)
            self.assertNotEqual(p.pk, self.gone.pk)

    def test_without_category_still_200(self):
        Product.objects.filter(pk=self.gone.pk).update(category=None)
        response = self.client.get("/producto/crema-retirada/")
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.context["alternatives"], [])

    def test_unknown_slug_is_still_404(self):
        self.assertEqual(self.client.get("/producto/no-existe/").status_code, 404)

    def test_active_product_still_renders_normal_page(self):
        response = self.client.get("/producto/alt-2/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalog/detail.html")

    def test_temporarily_out_of_stock_keeps_indexable_product_page(self):
        Product.objects.filter(pk=self.gone.pk).update(inactive_reason="sin_stock", stock=0)
        response = self.client.get("/producto/crema-retirada/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalog/detail.html")
        html = response.content.decode()
        self.assertNotIn("noindex", html)
        self.assertIn("https://schema.org/OutOfStock", html)

    def test_new_product_never_published_is_404(self):
        Product.objects.filter(pk=self.gone.pk).update(inactive_reason="sin_imagenes", gallery_synced_at=None)
        self.assertEqual(self.client.get("/producto/crema-retirada/").status_code, 404)

