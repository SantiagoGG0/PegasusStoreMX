from decimal import Decimal

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Category, Product

from .cart import Cart


class CartUpdateTests(TestCase):
    def setUp(self):
        self.client = Client()
        cat = Category.objects.create(dropi_id="c1", name="Test")
        self.cat = cat
        self.product = Product.objects.create(
            dropi_id=1001,
            name="Producto test",
            slug="producto-test",
            price=Decimal("50000"),
            stock=5,
            category=cat,
            is_active=True,
        )

    def test_cart_detail_shows_items(self):
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "quantity": 2,
                "price": str(self.product.price),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": "",
                "dropi_id": self.product.dropi_id,
                "supplier_id": 0,
                "local_id": self.product.pk,
                "stock": self.product.stock,
                "variation_id": None,
            }
        }
        session.save()
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Producto Test")
        self.assertContains(response, 'data-cart-key')
        self.assertContains(response, "data-cart-inc")

    def test_cart_add_rejects_out_of_stock(self):
        self.product.stock = 0
        self.product.save()
        url = reverse("cart:add", kwargs={"product_id": self.product.pk})
        response = self.client.post(url, {"quantity": 1})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.client.session.get("cart", {})), 0)

    def test_cart_update_quantity(self):
        session = self.client.session
        key = str(self.product.pk)
        session["cart"] = {
            key: {
                "quantity": 1,
                "price": str(self.product.price),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": "",
                "dropi_id": self.product.dropi_id,
                "supplier_id": 0,
                "local_id": self.product.pk,
                "stock": self.product.stock,
                "variation_id": None,
            }
        }
        session.save()
        response = self.client.post(
            reverse("cart:update"),
            {"cart_key": key, "action": "increment"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["lines"][0]["quantity"], 2)
        self.assertEqual(data["item_count"], 2)
        self.assertIn("summary_totals_html", data)
        self.assertIn("2 unidades", data["summary_totals_html"])
        cart = Cart(self.client)
        self.assertEqual(cart.cart[key]["quantity"], 2)

    def test_cart_summary_fragments_avoid_emoji(self):
        self._set_cart_with_product()

        response = self.client.post(
            reverse("cart:update"),
            {"cart_key": str(self.product.pk), "action": "increment"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        data = response.json()
        self.assertNotIn("🚚", data["shipping_groups_html"])
        self.assertNotIn("🎉", data["summary_totals_html"])

    def test_cart_update_caps_at_stock_in_view(self):
        key = str(self.product.pk)
        session = self.client.session
        session["cart"] = {
            key: {
                "quantity": 1,
                "price": str(self.product.price),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": "",
                "dropi_id": self.product.dropi_id,
                "supplier_id": 0,
                "local_id": self.product.pk,
                "stock": self.product.stock,
                "variation_id": None,
            }
        }
        session.save()
        self.client.post(
            reverse("cart:update"),
            {"cart_key": key, "quantity": "99"},
        )
        cart = Cart(self.client)
        self.assertEqual(cart.cart[key]["quantity"], 5)

    def test_cart_detail_paginates_suggested_products(self):
        self._set_cart_with_product()
        for i in range(15):
            Product.objects.create(
                dropi_id=1100 + i,
                name=f"Sugerido {i + 1}",
                slug=f"sugerido-{i + 1}",
                price=Decimal("25000"),
                stock=5,
                category=self.cat,
                is_active=True,
            )

        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["suggested_products"]), 12)
        self.assertTrue(response.context["suggested_page_obj"].has_next())
        self.assertContains(response, 'id="cart-suggested-load-more-wrap"')

    def test_cart_suggested_fragment_returns_next_page(self):
        self._set_cart_with_product()
        for i in range(15):
            Product.objects.create(
                dropi_id=1200 + i,
                name=f"Fragmento {i + 1}",
                slug=f"fragmento-{i + 1}",
                price=Decimal("25000"),
                stock=5,
                category=self.cat,
                is_active=True,
            )

        response = self.client.get(
            reverse("cart:suggested_fragment"),
            {"page": "2"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["html"].count('class="product-card"'), 3)
        self.assertEqual(data["loaded_count"], 15)
        self.assertEqual(data["total_count"], 15)
        self.assertFalse(data["has_next"])

    def test_cart_detail_groups_shipping_cost_by_supplier(self):
        other = Product.objects.create(
            dropi_id=1300,
            supplier_id=200,
            name="Proveedor envio B",
            slug="proveedor-envio-b",
            price=Decimal("30000"),
            stock=5,
            category=self.cat,
            is_active=True,
        )
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "quantity": 2,
                "price": str(self.product.price),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": "",
                "dropi_id": self.product.dropi_id,
                "supplier_id": 100,
                "local_id": self.product.pk,
                "stock": self.product.stock,
                "variation_id": None,
            },
            str(other.pk): {
                "quantity": 1,
                "price": str(other.price),
                "name": other.name,
                "slug": other.slug,
                "image": "",
                "dropi_id": other.dropi_id,
                "supplier_id": other.supplier_id,
                "local_id": other.pk,
                "stock": other.stock,
                "variation_id": None,
            },
        }
        session.save()

        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([group["supplier_id"] for group in response.context["shipping_groups"]], [100, 200])
        # Sin ciudad en sesión no se inventa un envío: se calcula en el checkout.
        self.assertEqual(
            response.context["shipping_groups"][0]["shipping_cost_label"],
            "Se calcula en el checkout según tu ciudad",
        )
        self.assertNotContains(response, "Incluido")

        # Con ciudad en sesión se muestra el envío real de cada bodega.
        session = self.client.session
        session["visitor_city"] = {"city": "Medellín", "state": "Antioquia"}
        session.save()
        labels = [g["shipping_cost_label"] for g in self.client.get(reverse("cart:detail")).context["shipping_groups"]]
        for label in labels:
            self.assertTrue(label == "Gratis" or label.startswith("$"), label)
        self.assertContains(response, "Costo de envío por bodega")
        # Supplier identity is intentionally not shown to the customer (generic label).
        self.assertContains(response, "Envío estándar")

    def test_cart_suggested_products_load_automatically(self):
        self._set_cart_with_product()
        for i in range(15):
            Product.objects.create(
                dropi_id=1400 + i,
                name=f"Auto carga {i + 1}",
                slug=f"auto-carga-{i + 1}",
                price=Decimal("25000"),
                stock=5,
                category=self.cat,
                is_active=True,
            )

        response = self.client.get(reverse("cart:detail"))

        self.assertContains(response, 'data-auto-load="true"')
        self.assertNotContains(response, "Cargar más productos")

    def test_cart_remove_requires_browser_confirmation(self):
        body = (
            settings.BASE_DIR / "templates" / "cart" / "partials" / "cart_body.html"
        ).read_text(encoding="utf-8")
        script = (settings.BASE_DIR / "static" / "js" / "cart-page.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="cart-remove-modal"', body)
        self.assertIn("askCartRemoveConfirm", script)
        self.assertIn("initCartPage", script)
        self.assertIn("data-cart-remove-confirm", body)

    def _set_cart_with_product(self):
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "quantity": 1,
                "price": str(self.product.price),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": "",
                "dropi_id": self.product.dropi_id,
                "supplier_id": self.product.supplier_id,
                "local_id": self.product.pk,
                "stock": self.product.stock,
                "variation_id": None,
            }
        }
        session.save()


class CartBuyNowTests(TestCase):
    def setUp(self):
        self.client = Client()
        cat = Category.objects.create(dropi_id="buy-cat", name="Buy")
        self.product = Product.objects.create(
            dropi_id=2001,
            name="Producto buy now",
            slug="producto-buy-now",
            price=Decimal("75000"),
            stock=4,
            category=cat,
            is_active=True,
        )

    def test_buy_now_adds_product_and_redirects_checkout(self):
        url = reverse("cart:buy_now", kwargs={"product_id": self.product.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("orders:checkout"))
        cart = Cart(self.client)
        self.assertEqual(len(cart), 1)
        self.assertEqual(cart.cart[str(self.product.pk)]["quantity"], 1)


class CartContentFragmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        cat = Category.objects.create(dropi_id="frag-cat", name="Frag")
        self.product = Product.objects.create(
            dropi_id=3001,
            name="Producto fragment",
            slug="producto-fragment",
            price=Decimal("40000"),
            stock=3,
            category=cat,
            is_active=True,
        )

    def test_content_fragment_requires_ajax(self):
        url = reverse("cart:content_fragment")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("cart:detail"))

    def test_content_fragment_empty_cart(self):
        url = reverse("cart:content_fragment")
        res = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["empty"])
        self.assertIn("cart-empty-state", data["html"])
        self.assertEqual(data["cart_count"], 0)

    def test_content_fragment_with_items(self):
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "quantity": 1,
                "price": str(self.product.price),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": "",
                "dropi_id": self.product.dropi_id,
                "supplier_id": 0,
                "local_id": self.product.pk,
                "stock": self.product.stock,
                "variation_id": None,
            }
        }
        session.save()
        url = reverse("cart:content_fragment")
        res = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["empty"])
        self.assertIn("cart-page", data["html"])
        self.assertIn("Producto Fragment", data["html"])
        self.assertEqual(data["cart_count"], 1)

    def test_empty_cart_detail_includes_refresh_script(self):
        template = (settings.BASE_DIR / "templates" / "cart" / "detail.html").read_text(
            encoding="utf-8"
        )
        body = (
            settings.BASE_DIR / "templates" / "cart" / "partials" / "cart_body.html"
        ).read_text(encoding="utf-8")
        refresh_js = (settings.BASE_DIR / "static" / "js" / "cart-empty-refresh.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("cart-empty-refresh.js", template)
        self.assertIn('id="cart-content"', template)
        self.assertIn("cart-empty-state", body)
        self.assertIn("cart:updated", refresh_js)
        self.assertIn("content_fragment", template)
