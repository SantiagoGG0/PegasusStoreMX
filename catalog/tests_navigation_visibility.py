from decimal import Decimal

from django.test import TestCase

from .models import Category, Product
from .navigation import get_nav_categories


class NavHidesCategoriesWithoutVisibleProductsTests(TestCase):
    """Bienestar íntimo (todo criterio e) no aparece en el menú mientras no
    tenga productos visibles; vuelve a aparecer en cuanto tenga uno."""

    def setUp(self):
        self.hogar = Category.objects.create(dropi_id="store:hogar", name="Hogar")
        self.intimo = Category.objects.create(dropi_id="store:bienestar_intimo", name="Bienestar íntimo")
        self._product(1, "lampara", self.hogar)
        self._product(2, "vibrador", self.intimo, seo_exclusion="e")
        self._product(3, "lubricante", self.intimo, seo_exclusion="e")

    def _product(self, dropi_id, slug, category, **kwargs):
        return Product.objects.create(
            dropi_id=dropi_id, name=slug, slug=slug, category=category, price=Decimal("30000"),
            cost=Decimal("10000"), stock=5, is_active=True, **kwargs,
        )

    def test_hidden_when_all_products_are_excluded(self):
        ids = [c.dropi_id for c in get_nav_categories()]
        self.assertIn("store:hogar", ids)
        self.assertNotIn("store:bienestar_intimo", ids)
        html = self.client.get("/").content.decode()
        self.assertNotIn("?category=store:bienestar_intimo", html)

    def test_reappears_with_a_visible_product(self):
        self._product(4, "masajeador-cuello", self.intimo)
        self.assertIn("store:bienestar_intimo", [c.dropi_id for c in get_nav_categories()])

    def test_image_flagged_products_do_not_count(self):
        Product.objects.filter(slug="lampara").update(image_flagged=True)
        self.assertNotIn("store:hogar", [c.dropi_id for c in get_nav_categories()])
