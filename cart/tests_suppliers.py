from decimal import Decimal
from unittest.mock import patch

from django.db.models.query import QuerySet
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Category, Product

from .cart import Cart
from .recommendations import products_for_cart
from .suppliers import validate_supplier_for_add


class SupplierRulesTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="sup-cat", name="Cat")
        self.p1 = Product.objects.create(
            dropi_id=2001,
            supplier_id=100,
            name="Proveedor A",
            slug="prod-a",
            price=Decimal("10000"),
            stock=5,
            category=self.cat,
            is_active=True,
        )
        self.p2 = Product.objects.create(
            dropi_id=2002,
            supplier_id=100,
            name="Otro A",
            slug="prod-a2",
            price=Decimal("20000"),
            stock=5,
            category=self.cat,
            is_active=True,
        )
        self.p3 = Product.objects.create(
            dropi_id=2003,
            supplier_id=200,
            name="Proveedor B",
            slug="prod-b",
            price=Decimal("30000"),
            stock=5,
            category=self.cat,
            is_active=True,
        )
        self.p4 = Product.objects.create(
            dropi_id=2004,
            supplier_id=300,
            name="Proveedor C",
            slug="prod-c",
            price=Decimal("40000"),
            stock=5,
            category=self.cat,
            is_active=True,
        )

    def _cart_with(self, client: Client, *products):
        session = client.session
        cart_data = {}
        for p in products:
            cart_data[str(p.pk)] = {
                "quantity": 1,
                "price": str(p.price),
                "name": p.name,
                "slug": p.slug,
                "image": "",
                "dropi_id": p.dropi_id,
                "supplier_id": p.supplier_id,
                "local_id": p.pk,
                "stock": p.stock,
                "variation_id": None,
            }
        session["cart"] = cart_data
        session.save()

    def test_second_supplier_warns(self):
        client = Client()
        self._cart_with(client, self.p1)
        cart = Cart(client)
        ok, err, warn = validate_supplier_for_add(cart.cart, self.p3)
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertIn("guía", warn.lower())

    def test_third_supplier_warns_without_blocking(self):
        client = Client()
        self._cart_with(client, self.p1, self.p3)
        cart = Cart(client)
        ok, err, warn = validate_supplier_for_add(cart.cart, self.p4)
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertIn("varias bodegas", warn.lower())

    def test_quick_add_returns_warning_json(self):
        client = Client()
        self._cart_with(client, self.p1)
        url = reverse("cart:add_quick", kwargs={"product_id": self.p3.pk})
        res = client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["warning"])

    def test_recommendations_prioritize_same_supplier(self):
        client = Client()
        self._cart_with(client, self.p1)
        cart = Cart(client)
        suggested, primary = products_for_cart(cart, limit=10)
        self.assertEqual(primary, 100)
        if suggested:
            self.assertEqual(suggested[0].supplier_id, 100)

    def test_recommendations_do_not_use_server_side_iterator(self):
        client = Client()
        self._cart_with(client, self.p1)
        cart = Cart(client)

        with patch.object(QuerySet, "iterator", side_effect=AssertionError("no server-side cursors")):
            suggested, primary = products_for_cart(cart, limit=10)

        self.assertEqual(primary, 100)
        self.assertTrue(suggested)
