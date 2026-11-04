from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django import forms
from django.core.cache import cache, caches
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product

from .forms import CheckoutForm
from .models import Order

User = get_user_model()


class OrderCancelTests(TestCase):
    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        self.order = Order.objects.create(
            name="Ana",
            surname="Lopez",
            email="ana@example.com",
            phone="5512345678",
            address="Calle 1",
            city="Guadalajara",
            state="JAL",
            total=Decimal("100000"),
            items=[],
            status=Order.STATUS_PENDING,
        )

    def test_can_cancel_within_window(self):
        self.assertTrue(self.order.can_cancel())

    def test_cannot_cancel_after_window(self):
        self.order.created_at = timezone.now() - timedelta(minutes=20)
        self.order.save()
        self.assertFalse(self.order.can_cancel())

    @patch("orders.views.DropiClient")
    def test_cancel_view_posts(self, mock_client_cls):
        mock_client_cls.return_value.cancel_order.return_value = {"isSuccess": True}
        url = reverse("orders:cancel", kwargs={"access_token": self.order.access_token})
        response = self.client.post(url, {"cancel_reason": "Error"})
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CANCELLED)
        self.assertIsNotNone(self.order.cancelled_at)


class OrderPagesTests(TestCase):
    def test_confirmation_page(self):
        order = Order.objects.create(
            name="A",
            surname="B",
            email="a@b.com",
            phone="1",
            address="x",
            city="y",
            state="z",
            total=Decimal("1"),
            items=[],
        )
        url = reverse("orders:confirmation", kwargs={"access_token": order.access_token})
        self.assertEqual(self.client.get(url).status_code, 200)


class PagesLegalTests(TestCase):
    def test_legal_pages_load(self):
        for name in (
            "pages:intellectual_property",
            "pages:refunds",
            "pages:privacy",
            "pages:terms",
            "pages:trust",
        ):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)


class OrderTrackTests(TestCase):
    def test_track_by_guide_number_redirects_to_detail(self):
        order = Order.objects.create(
            name="A",
            surname="B",
            email="buyer@example.com",
            phone="5512345678",
            address="x",
            city="y",
            state="z",
            total=Decimal("1"),
            items=[],
            shipping_guide="9402 8173 6602",
        )
        url = reverse("orders:track")
        response = self.client.post(url, {"guide": "9402817366 02"})
        self.assertRedirects(response, reverse("orders:detail", kwargs={"access_token": order.access_token}))

    def test_track_with_unknown_guide_shows_error(self):
        url = reverse("orders:track")
        response = self.client.post(url, {"guide": "0000000000"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No encontramos ese número")


class CheckoutFormTests(TestCase):
    _BASE_DATA = {
        "name": "Ana",
        "surname": "Lopez",
        "email": "ana@example.com",
        "phone": "5512345678",
        "address": "Calle 1",
        "state": "CMX",
        "city": "Cuauhtémoc",
        "zip_code": "99999", "payment_method": Order.PAYMENT_COD,
        "accept_terms": True,
    }

    def test_city_is_a_hidden_text_field(self):
        form = CheckoutForm()
        self.assertIsInstance(form.fields["city"], forms.CharField)
        self.assertIsInstance(form.fields["city"].widget, forms.HiddenInput)

    def test_payment_method_is_hidden_when_only_cod_available(self):
        """A single-choice radio has nothing to choose — it used to render as
        a bare native radio button sitting right above the styled COD box,
        duplicating "Pago contra entrega" on screen. With only COD enabled
        (the default), the field should be a hidden input, not a radio."""
        form = CheckoutForm()
        self.assertIsInstance(form.fields["payment_method"].widget, forms.HiddenInput)
        self.assertEqual(form.fields["payment_method"].initial, Order.PAYMENT_COD)

    def test_submit_without_city_fails_validation(self):
        data = {**self._BASE_DATA, "city": ""}
        form = CheckoutForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("city", form.errors)

    def test_valid_city_for_department_is_accepted(self):
        data = {**self._BASE_DATA, "state": "AGU", "city": "Asientos"}
        form = CheckoutForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["city"], "Asientos")

    def test_city_name_is_normalized_to_canonical_spelling(self):
        data = {**self._BASE_DATA, "state": "JAL", "city": "tlajomulco de zuniga"}
        form = CheckoutForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["city"], "Tlajomulco de Zúñiga")

    def test_city_from_another_department_corrects_the_department(self):
        # Guadalajara solo existe en Jalisco: con Aguascalientes elegido se
        # corrige el estado en vez de perder la venta.
        data = {**self._BASE_DATA, "state": "AGU", "city": "Guadalajara"}
        form = CheckoutForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual((form.cleaned_data["state"], form.cleaned_data["city"]), ("JAL", "Guadalajara"))

    def test_unknown_city_fails_validation(self):
        form = CheckoutForm(data={**self._BASE_DATA, "state": "AGU", "city": "Ciudad Inventada"})
        self.assertFalse(form.is_valid())
        self.assertIn("city", form.errors)

    def test_every_department_has_cities_available(self):
        from .forms import CITIES_BY_DEPARTMENT_CODE, COLOMBIA_DEPARTMENTS

        for code, name in COLOMBIA_DEPARTMENTS:
            if not code:
                continue
            self.assertTrue(
                CITIES_BY_DEPARTMENT_CODE.get(code),
                f"{name} ({code}) has no cities",
            )

    def test_department_code_for_city_name(self):
        from .forms import department_code_for_city_name

        self.assertEqual(department_code_for_city_name("Guadalajara"), "JAL")
        self.assertEqual(department_code_for_city_name("Asientos"), "AGU")

    def test_zip_code_is_required_and_has_five_digits(self):
        form = CheckoutForm(data={**self._BASE_DATA, "zip_code": ""})
        self.assertIn("zip_code", form.errors)
        form = CheckoutForm(data={**self._BASE_DATA, "zip_code": "123"})
        self.assertIn("zip_code", form.errors)

    def test_zip_code_with_lost_leading_zero_is_completed(self):
        # "6600" copiado de una hoja de cálculo que quitó el 0 inicial.
        form = CheckoutForm(data={**self._BASE_DATA, "zip_code": "6600"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["zip_code"], "06600")

    def test_known_zip_fills_state_and_city(self):
        # Sin municipio elegido, el CP de Dropi lo completa en vez de rechazar.
        form = CheckoutForm(data={**self._BASE_DATA, "state": "", "city": "", "zip_code": "44100"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual((form.cleaned_data["state"], form.cleaned_data["city"]), ("JAL", "Guadalajara"))

    def test_known_zip_does_not_override_a_valid_city(self):
        # El CP de Dropi no está completo: si el municipio elegido existe, manda.
        form = CheckoutForm(data={**self._BASE_DATA, "state": "NLE", "city": "Monterrey", "zip_code": "44100"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual((form.cleaned_data["state"], form.cleaned_data["city"]), ("NLE", "Monterrey"))


class CheckoutCityDepartmentIntegrationTests(TestCase):
    """De punta a punta: un municipio pequeño (Asientos, Aguascalientes)
    completa la compra y a Dropi le llegan sus nombres exactos."""

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        cat = Category.objects.create(name="Ropa", dropi_id=1)
        self.product = Product.objects.create(
            dropi_id=2001,
            name="Producto checkout test",
            slug="producto-checkout-test",
            price=Decimal("50000"),
            cost=Decimal("30000"),
            stock=5,
            category=cat,
            is_active=True,
        )

    def _seed_cart(self):
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "quantity": 1,
                "price": str(self.product.price),
                "cost": str(self.product.cost),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": self.product.main_image,
                "dropi_id": self.product.dropi_id,
                "supplier_id": self.product.supplier_id,
                "local_id": self.product.pk,
                "stock": 5,
                "variation_id": None,
                "variation_label": "",
            }
        }
        session.save()

    @patch("orders.views.DropiClient")
    def test_checkout_post_creates_order_for_non_major_city(self, mock_client_cls):
        mock_client_cls.return_value.get_product.return_value = {
            "objects": {"warehouse_product": [{"stock": 5, "warehouse_id": 8120}]}
        }
        mock_client_cls.return_value.create_order.return_value = {"objects": {"id": 999}}
        self._seed_cart()

        data = {
            "name": "Claudia",
            "surname": "Gomez",
            "email": "claudia@example.com",
            "phone": "5512345678",
            "address": "calle 49e #83a-91",
            "state": "AGU",
            "city": "Asientos",
            "zip_code": "99999", "payment_method": Order.PAYMENT_COD,
            "accept_terms": "on",
        }
        response = self.client.post(reverse("orders:checkout"), data)
        if response.status_code != 302:
            self.fail(response.context["form"].errors)

        order = Order.objects.latest("id")
        self.assertEqual(order.city, "Asientos")
        self.assertEqual(order.state, "AGU")

        sent_payload = mock_client_cls.return_value.create_order.call_args[0][0]
        self.assertEqual(sent_payload["products"][0]["warehouse_id"], 8120)
        # Dropi México valida contra su catálogo: nombres de Dropi, no los visibles.
        self.assertEqual(
            (sent_payload["country"], sent_payload["state"], sent_payload["city"], sent_payload["zip_code"]),
            ("MX", "AGUASCALIENTES", "ASIENTOS", "99999"),
        )

    @patch("orders.views.DropiClient")
    def test_shipping_shown_at_checkout_is_collected_on_delivery(self, mock_client_cls):
        """Pedido #92 de Colombia: el cliente vio el total con envío y Dropi
        recibió solo los productos, el envío nunca se cobraba. Aquí: 2 × $249
        (costo $130) a Guadalajara, guía $188: margen 238, piso 2 × 85 →
        envío 188 + 170 − 238 = $120, total $618."""
        Product.objects.filter(pk=self.product.pk).update(price=Decimal("249"), cost=Decimal("130"))
        self.product.refresh_from_db()
        mock_client_cls.return_value.get_product.return_value = {
            "objects": {"warehouse_product": [{"stock": 5, "warehouse_id": 8120}]}
        }
        mock_client_cls.return_value.create_order.return_value = {"objects": {"id": 999, "shipping_amount": 13915}}
        self._seed_cart()
        session = self.client.session
        session["cart"][str(self.product.pk)]["quantity"] = 2
        session.save()

        data = {
            "name": "Ana", "surname": "Ruiz", "email": "ana@example.com", "phone": "5512345678",
            "address": "Av. Juárez 1", "state": "JAL", "city": "Guadalajara",
            "zip_code": "99999", "payment_method": Order.PAYMENT_COD, "accept_terms": "on",
        }
        response = self.client.post(reverse("orders:checkout"), data)
        if response.status_code != 302:
            self.fail(response.context["form"].errors)

        sent_payload = mock_client_cls.return_value.create_order.call_args[0][0]
        self.assertEqual(sent_payload["total_order"], 618)
        # Dropi cobra la suma de los productos, no total_order (pedido #100).
        self.assertEqual(sum(p["price"] * p["quantity"] for p in sent_payload["products"]), 618)
        order = Order.objects.latest("id")
        self.assertEqual(order.shipping_cost, Decimal("120"))
        self.assertEqual(order.total, Decimal("618"))

    def test_checkout_post_rejects_city_that_does_not_exist(self):
        # Una ciudad de otro departamento se corrige sola (ver
        # CheckoutDoesNotLoseSalesTests); una que no existe se rechaza.
        self._seed_cart()
        data = {
            "name": "Claudia",
            "surname": "Gomez",
            "email": "claudia@example.com",
            "phone": "5512345678",
            "address": "calle 49e #83a-91",
            "state": "JAL",
            "city": "Ciudad Inventada",
            "zip_code": "99999", "payment_method": Order.PAYMENT_COD,
            "accept_terms": "on",
        }
        response = self.client.post(reverse("orders:checkout"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("city", response.context["form"].errors)

    def test_checkout_get_exposes_cities_scoped_by_department(self):
        self._seed_cart()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        cities_by_dept = response.context["cities_by_department_json"]
        self.assertIn("Asientos", cities_by_dept)
        self.assertIn("AGU", cities_by_dept)


class CheckoutVariantOutOfStockTests(TestCase):
    """Reproduces a real production failure: a variable product whose
    aggregate stock is large but the specific ordered variant (color/size)
    has zero stock in its own warehouses. Dropi's order-creation endpoint
    correctly rejects this ("Producto no posee stock en ninguna de sus
    bodegas"), but before the fix our own pre-checks let it through because
    they fell back to the product-level aggregate whenever the per-variant
    number was zero, masking the real shortage."""

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        cat = Category.objects.create(name="Ropa interior", dropi_id=1)
        self.product = Product.objects.create(
            dropi_id=2110693,
            name="Brasier Reafirmante sin Varillas",
            slug="brasier-reafirmante-sin-varillas",
            price=Decimal("39000"),
            cost=Decimal("20000"),
            stock=11959,  # aggregate across every color/size combo
            category=cat,
            is_active=True,
            variants=[
                {
                    "id": 2059262,
                    "attribute_values": [{"value": "Beigge / L"}],
                    "warehouse_product_variation": [{"stock": 0}],
                }
            ],
        )

    def _seed_cart(self):
        session = self.client.session
        session["cart"] = {
            f"{self.product.pk}_2059262": {
                "quantity": 1,
                "price": str(self.product.price),
                "cost": str(self.product.cost),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": self.product.main_image,
                "dropi_id": self.product.dropi_id,
                "supplier_id": self.product.supplier_id,
                "local_id": self.product.pk,
                "stock": 0,
                "variation_id": 2059262,
                "variation_label": "Beigge / L",
            }
        }
        session.save()

    @patch("orders.views.DropiClient")
    def test_checkout_blocks_before_submitting_to_dropi(self, mock_client_cls):
        self._seed_cart()
        data = {
            "name": "Claudia",
            "surname": "Gomez",
            "email": "claudia@example.com",
            "phone": "5512345678",
            "address": "calle 49e #83a-91",
            "state": "JAL",
            "city": "Guadalajara",
            "zip_code": "99999", "payment_method": Order.PAYMENT_COD,
            "accept_terms": "on",
        }
        response = self.client.post(reverse("orders:checkout"), data, follow=True)
        # cart.refresh_from_db() prunes the out-of-stock variant before the
        # form is even validated, so checkout bounces back to the catalog
        # with a "se agotó" warning instead of ever reaching Dropi.
        self.assertContains(response, "agotó")
        mock_client_cls.return_value.create_order.assert_not_called()
        self.assertEqual(Order.objects.count(), 0)
        self.assertNotIn(f"{self.product.pk}_2059262", self.client.session.get("cart", {}))


class CheckoutWarehouseIdTests(TestCase):
    """Dropi's order-creation endpoint needs to know which warehouse to pull
    stock from. We previously sent no warehouse_id at all ("let Dropi
    determine from supplier"), which this incident shows isn't reliable —
    products with confirmed real stock still got rejected as out of stock.
    This locks in that the per-item warehouse_id is resolved from the live
    Dropi payload (not guessed) and reaches the order payload correctly,
    including when two variants of the same product are in the cart."""

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        cat = Category.objects.create(name="Ropa interior", dropi_id=1)
        self.product = Product.objects.create(
            dropi_id=2110693,
            name="Brasier Reafirmante sin Varillas",
            slug="brasier-reafirmante-sin-varillas",
            price=Decimal("39000"),
            cost=Decimal("20000"),
            stock=11959,
            category=cat,
            is_active=True,
            variants=[
                {
                    "id": 2059262,
                    "attribute_values": [{"value": "Beigge / Xxl"}],
                    "warehouse_product_variation": [{"warehouse_id": 191, "stock": 451}],
                }
            ],
        )

    def _seed_cart(self):
        session = self.client.session
        session["cart"] = {
            f"{self.product.pk}_2059262": {
                "quantity": 1,
                "price": str(self.product.price),
                "cost": str(self.product.cost),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": self.product.main_image,
                "dropi_id": self.product.dropi_id,
                "supplier_id": self.product.supplier_id,
                "local_id": self.product.pk,
                "stock": 451,
                "variation_id": 2059262,
                "variation_label": "Beigge / Xxl",
            }
        }
        session.save()

    @patch("orders.views.DropiClient")
    def test_variant_warehouse_id_reaches_dropi_payload(self, mock_client_cls):
        mock_client_cls.return_value.get_product.return_value = {
            "objects": {
                "variations": [
                    {
                        "id": 2059262,
                        "warehouse_product_variation": [{"warehouse_id": 191, "stock": 451}],
                    },
                    {
                        "id": 2059261,
                        "warehouse_product_variation": [{"warehouse_id": 8119, "stock": 187}],
                    },
                ]
            }
        }
        mock_client_cls.return_value.create_order.return_value = {"objects": {"id": 999}}
        self._seed_cart()

        data = {
            "name": "Claudia",
            "surname": "Gomez",
            "email": "claudia@example.com",
            "phone": "5512345678",
            "address": "calle 49e #83a-91",
            "state": "JAL",
            "city": "Guadalajara",
            "zip_code": "99999", "payment_method": Order.PAYMENT_COD,
            "accept_terms": "on",
        }
        response = self.client.post(reverse("orders:checkout"), data)
        if response.status_code != 302:
            self.fail(response.context["form"].errors)

        sent_payload = mock_client_cls.return_value.create_order.call_args[0][0]
        line = sent_payload["products"][0]
        self.assertEqual(line["variation_id"], 2059262)
        # Must resolve THIS variant's own warehouse (191), not its sibling's (8119).
        self.assertEqual(line["warehouse_id"], 191)


class CheckoutMultiSupplierSplitTests(TestCase):
    """Dropi does not support combining products from different suppliers in
    one order — confirmed in production: a two-supplier cart always got
    rejected with "Producto no posee stock en ninguna de sus bodegas" even
    though every product had real, verified stock. checkout() must submit
    one Dropi order per supplier instead of one combined order."""

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        cat = Category.objects.create(name="Mixto", dropi_id=1)
        self.product_a = Product.objects.create(
            dropi_id=2110693,
            supplier_id=32665,
            name="Brasier Reafirmante sin Varillas",
            slug="brasier-reafirmante-sin-varillas",
            price=Decimal("39000"),
            cost=Decimal("20000"),
            stock=638,
            category=cat,
            is_active=True,
        )
        self.product_b = Product.objects.create(
            dropi_id=2201176,
            supplier_id=231330,
            name="Contadora de Billetes pro 2 en 1",
            slug="contadora-de-billetes-pro-2-en-1",
            price=Decimal("380000"),
            cost=Decimal("179900"),
            stock=90,
            category=cat,
            is_active=True,
        )

    def _seed_cart(self):
        session = self.client.session
        session["cart"] = {
            str(self.product_a.pk): {
                "quantity": 1,
                "price": str(self.product_a.price),
                "cost": str(self.product_a.cost),
                "name": self.product_a.name,
                "slug": self.product_a.slug,
                "image": self.product_a.main_image,
                "dropi_id": self.product_a.dropi_id,
                "supplier_id": self.product_a.supplier_id,
                "local_id": self.product_a.pk,
                "stock": 638,
                "variation_id": None,
                "variation_label": "",
            },
            str(self.product_b.pk): {
                "quantity": 1,
                "price": str(self.product_b.price),
                "cost": str(self.product_b.cost),
                "name": self.product_b.name,
                "slug": self.product_b.slug,
                "image": self.product_b.main_image,
                "dropi_id": self.product_b.dropi_id,
                "supplier_id": self.product_b.supplier_id,
                "local_id": self.product_b.pk,
                "stock": 90,
                "variation_id": None,
                "variation_label": "",
            },
        }
        session.save()

    def _checkout_data(self):
        return {
            "name": "Claudia",
            "surname": "Gomez",
            "email": "claudia@example.com",
            "phone": "5512345678",
            "address": "calle 49e #83a-91",
            "state": "JAL",
            "city": "Guadalajara",
            "zip_code": "99999", "payment_method": Order.PAYMENT_COD,
            "accept_terms": "on",
        }

    @patch("orders.views.DropiClient")
    def test_two_suppliers_produce_two_separate_dropi_orders(self, mock_client_cls):
        mock_client_cls.return_value.get_product.return_value = {
            "objects": {"warehouse_product": [{"stock": 100, "warehouse_id": 1}]}
        }
        mock_client_cls.return_value.create_order.return_value = {"objects": {"id": 999}}
        self._seed_cart()

        response = self.client.post(reverse("orders:checkout"), self._checkout_data())
        if response.status_code != 302:
            self.fail(response.context["form"].errors)

        self.assertEqual(mock_client_cls.return_value.create_order.call_count, 2)
        orders = list(Order.objects.order_by("pk"))
        self.assertEqual(len(orders), 2)

        # Same checkout, so both orders share a group_token...
        self.assertEqual(orders[0].group_token, orders[1].group_token)
        # ...but each Dropi payload only carries its own supplier's product.
        sent_payloads = [c.args[0] for c in mock_client_cls.return_value.create_order.call_args_list]
        dropi_ids_per_call = [{p["id"] for p in payload["products"]} for payload in sent_payloads]
        self.assertIn({2110693}, dropi_ids_per_call)
        self.assertIn({2201176}, dropi_ids_per_call)

    @patch("orders.views.DropiClient")
    def test_one_supplier_failing_does_not_block_the_other(self, mock_client_cls):
        mock_client_cls.return_value.get_product.return_value = {
            "objects": {"warehouse_product": [{"stock": 100, "warehouse_id": 1}]}
        }

        from dropi_client import DropiAPIError

        def create_order_side_effect(payload):
            product_ids = {p["id"] for p in payload["products"]}
            if 2201176 in product_ids:
                raise DropiAPIError("Producto no posee stock en ninguna de sus bodegas")
            return {"objects": {"id": 999}}

        mock_client_cls.return_value.create_order.side_effect = create_order_side_effect
        self._seed_cart()

        response = self.client.post(reverse("orders:checkout"), self._checkout_data())
        if response.status_code != 302:
            self.fail(response.context["form"].errors)

        orders = list(Order.objects.order_by("pk"))
        self.assertEqual(len(orders), 2)
        # El que Dropi rechazó no se cancela: queda pendiente para crearlo a mano.
        succeeded = [o for o in orders if not o.needs_manual_supplier]
        failed = [o for o in orders if o.needs_manual_supplier]
        self.assertEqual(len(succeeded), 1)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].status, Order.STATUS_PENDING)
        self.assertIn("Crear a mano en Dropi", failed[0].cancel_reason)
        # The successful order still redirects to a working confirmation.
        self.assertEqual(response.url, reverse("orders:confirmation", args=[succeeded[0].access_token]))

    @patch("orders.views.DropiClient")
    def test_confirmation_page_shows_sibling_orders(self, mock_client_cls):
        mock_client_cls.return_value.get_product.return_value = {
            "objects": {"warehouse_product": [{"stock": 100, "warehouse_id": 1}]}
        }
        mock_client_cls.return_value.create_order.return_value = {"objects": {"id": 999}}
        self._seed_cart()

        response = self.client.post(reverse("orders:checkout"), self._checkout_data())
        order = Order.objects.order_by("pk").first()

        confirmation = self.client.get(reverse("orders:confirmation", args=[order.access_token]))
        self.assertEqual(confirmation.status_code, 200)
        self.assertEqual(len(confirmation.context["sibling_orders"]), 1)
        self.assertContains(confirmation, "dividió en 2 envíos")


class CheckoutShippingExperimentTests(TestCase):
    """needs_combo bucket only: checkout must show the same 'envío real +
    razón' block as the product detail page, and log exactly one 'shown'
    event per real page view (not per POST validation retry)."""

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        cat = Category.objects.create(dropi_id="shipexp-checkout", name="Categoria Combo Checkout")
        # margin=500 -> shipping_gap 19500 > SHIPPING_CEILING (18000) -> needs_combo
        self.product = Product.objects.create(
            dropi_id=777101,
            name="Producto Checkout Margen Bajo",
            slug="producto-checkout-margen-bajo",
            category=cat,
            price=Decimal("10500"),
            cost=Decimal("10000"),
            stock=10,
            is_active=True,
        )

    def _seed_cart(self):
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "quantity": 1,
                "price": str(self.product.price),
                "cost": str(self.product.cost),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": self.product.main_image,
                "dropi_id": self.product.dropi_id,
                "supplier_id": self.product.supplier_id,
                "local_id": self.product.pk,
                "stock": self.product.stock,
            }
        }
        session.save()

    def test_checkout_get_shows_experiment_block_and_logs_once(self):
        from catalog.models import ShippingExperimentEvent

        self._seed_cart()
        session = self.client.session
        session["visitor_city"] = {"city": "Tepic", "state": "Nayarit"}
        session.save()
        response = self.client.get(reverse("orders:checkout"))
        self.assertContains(response, "shipping-experiment")
        self.assertEqual(
            ShippingExperimentEvent.objects.filter(
                product=self.product, event_type=ShippingExperimentEvent.EVENT_SHOWN
            ).count(),
            1,
        )

        # A second GET (e.g. reload) logs a second impression — it's a raw
        # "how many times shown" counter, not a per-session unique count.
        self.client.get(reverse("orders:checkout"))
        self.assertEqual(
            ShippingExperimentEvent.objects.filter(
                product=self.product, event_type=ShippingExperimentEvent.EVENT_SHOWN
            ).count(),
            2,
        )

    def test_checkout_post_validation_error_does_not_log_shown(self):
        from catalog.models import ShippingExperimentEvent

        self._seed_cart()
        # Missing required fields -> form invalid -> falls through to the
        # same render() as GET, but must NOT count as a new impression.
        self.client.post(reverse("orders:checkout"), {"name": "Solo nombre"})
        self.assertFalse(ShippingExperimentEvent.objects.exists())


class CheckoutPaymentMethodRenderTests(TestCase):
    """Regresión visual: con solo COD habilitado, el checkout mostraba un
    radio button nativo sin estilo justo encima de la caja verde
    "Pago contra entrega" — el mismo texto repetido dos veces en el momento
    exacto de pagar. Ver CheckoutFormTests.test_payment_method_is_hidden_when_only_cod_available
    para el fix a nivel de formulario."""

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        cat = Category.objects.create(dropi_id="pm-render-1", name="Categoria PM")
        self.product = Product.objects.create(
            dropi_id=888201,
            name="Producto Checkout PM",
            slug="producto-checkout-pm",
            category=cat,
            price=Decimal("50000"),
            cost=Decimal("20000"),
            stock=10,
            is_active=True,
        )
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "quantity": 1,
                "price": str(self.product.price),
                "cost": str(self.product.cost),
                "name": self.product.name,
                "slug": self.product.slug,
                "image": self.product.main_image,
                "dropi_id": self.product.dropi_id,
                "supplier_id": self.product.supplier_id,
                "local_id": self.product.pk,
                "stock": self.product.stock,
            }
        }
        session.save()

    def test_no_visible_payment_radio_when_only_cod(self):
        response = self.client.get(reverse("orders:checkout"))
        html = response.content.decode()
        self.assertNotIn('type="radio" name="payment_method"', html)
        self.assertIn('type="hidden" name="payment_method"', html)

    def test_without_city_shipping_is_not_shown_as_free_or_estimated(self):
        # Sin ciudad el cálculo usa la zona C: mostrar "Gratis" o ese monto
        # confundía, igual que la nota de "zona remota".
        html = self.client.get(reverse("orders:checkout")).content.decode()
        self.assertIn("Elige tu ciudad para ver el envío", html)
        self.assertIn("Total sin envío", html)
        self.assertNotIn("Gratis", html)
        self.assertNotIn("zona remota", html)

    def test_with_city_shows_shipping_and_total(self):
        session = self.client.session
        session["visitor_city"] = {"city": "Guadalajara", "state": "Jalisco"}
        session.save()
        html = self.client.get(reverse("orders:checkout")).content.decode()
        self.assertNotIn("Elige tu ciudad para ver el envío", html)
        self.assertIn("Total al recibir", html)

    def test_ga4_begin_checkout_only_on_initial_load(self):
        html = self.client.get(reverse("orders:checkout")).content.decode()
        self.assertIn("'begin_checkout'", html)
        self.assertIn("'add_shipping_info'", html)

    def test_ga4_logs_server_validation_errors_by_field_name(self):
        html = self.client.post(reverse("orders:checkout"), {"payment_method": "CON RECAUDO"}).content.decode()
        self.assertNotIn("gtag('event', 'begin_checkout'", html)
        self.assertIn("'checkout_validation_error'", html)
        for field in ("name", "phone", "address", "state", "city"):
            self.assertIn(f"'{field}'", html)
        self.assertIn("checkout-cod-box__title", html)


class PurchaseTrackingTests(TestCase):
    """El evento de compra se renderiza una sola vez por checkout: antes salía
    duplicado en cada vista (bloques anidados en content) y otra vez en cada
    recarga del polling."""

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        self.order = Order.objects.create(
            name="A", surname="B", phone="5512345678", address="x",
            city="Guadalajara", state="JAL", total=Decimal("54400"),
            shipping_cost=Decimal("4400"),
            items=[{"product_id": 7, "name": "Crema", "price": "50000", "quantity": 1, "total": "50000"}],
        )
        self.url = reverse("orders:confirmation", kwargs={"access_token": self.order.access_token})

    def _flag_checkout(self):
        session = self.client.session
        session["purchase_to_track"] = str(self.order.group_token)
        session.save()

    @patch("orders.views.try_sync_order")
    def test_purchase_fires_once_on_first_view_only(self, _sync):
        self._flag_checkout()
        first = self.client.get(self.url).content.decode()
        self.assertEqual(first.count("'purchase'"), 1)
        self.assertIn("eventID: eventId", first)
        self.assertIn("parseFloat('54400.00')", first)
        again = self.client.get(self.url).content.decode()
        self.assertNotIn("'purchase'", again)

    @patch("orders.views.try_sync_order")
    def test_no_purchase_without_checkout_flag(self, _sync):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("'purchase'", html)

    @patch("orders.views.try_sync_order")
    def test_status_polling_does_not_reload_page(self, _sync):
        html = self.client.get(self.url).content.decode()
        self.assertEqual(html.count("var pollUrl"), 1)
        self.assertNotIn("location.reload", html)

    @patch("orders.views.try_sync_order")
    def test_ads_conversion_only_when_configured(self, _sync):
        self._flag_checkout()
        self.assertNotIn("'conversion'", self.client.get(self.url).content.decode())
        self._flag_checkout()
        with override_settings(GOOGLE_ADS_PURCHASE_SEND_TO="AW-123/abc"):
            html = self.client.get(self.url).content.decode()
        self.assertIn(r"send_to: 'AW\u002D123/abc'", html)  # escapejs escapa el "-"


class OrderDetailPollingTests(TestCase):
    """orders/detail.html tenía extra_scripts anidado dentro de content: el
    polling corría dos veces y recargaba la página en cada cambio."""

    @patch("orders.views.try_sync_order")
    def test_single_poll_and_no_reload(self, _sync):
        order = Order.objects.create(
            name="A", surname="B", phone="5512345678", address="x",
            city="Guadalajara", state="JAL", total=Decimal("1"), items=[],
            shipping_guide="GU1",
        )
        html = self.client.get(reverse("orders:detail", kwargs={"access_token": order.access_token})).content.decode()
        self.assertEqual(html.count("var pollUrl"), 1)
        self.assertNotIn("location.reload", html)
        self.assertEqual(html.count("function copyGuide"), 1)


class PurchaseTrackingLoadsImmediatelyTests(TestCase):
    def test_checkout_page_does_not_defer_measurement_scripts(self):
        cat = Category.objects.create(name="Otros", dropi_id="store:otros")
        product = Product.objects.create(dropi_id=9001, name="P", slug="p-track", price=Decimal("50000"),
                                         cost=Decimal("20000"), stock=5, category=cat, is_active=True)
        session = self.client.session
        session["cart"] = {str(product.pk): {
            "quantity": 1, "price": "50000", "cost": "20000", "name": "P", "slug": "p-track", "image": "",
            "dropi_id": 9001, "supplier_id": 0, "local_id": product.pk, "stock": 5,
            "variation_id": None, "variation_label": "",
        }}
        session.save()
        html = self.client.get(reverse("orders:checkout")).content.decode()
        self.assertIn("window.PGS_TRACK_NOW = true", html)
        self.assertLess(html.index("window.PGS_TRACK_NOW = true"), html.index("window.pgsAfterLoad"))


# Transportadoras de ejemplo: en México la lista real está vacía hasta conocer
# las de la cuenta de Dropi México (ver orders/services.CARRIER_FALLBACKS).
SAMPLE_CARRIERS = [(2, "ENVIA"), (5, "ESTAFETA"), (3, "PAQUETEXPRESS")]


class CarrierFallbackTests(TestCase):
    """Dropi rechaza la orden cuando la transportadora predeterminada no tiene
    contra entrega en la ciudad: se reintenta con otras transportadoras."""

    CITY_ERROR = "3. La ciudad no tiene habilitado el médoto de envío: CON RECAUDO - TEPIC-NAYARIT-OTRA-[]-"

    def test_mexico_has_no_colombian_carrier_ids(self):
        from orders.services import CARRIER_FALLBACKS

        self.assertEqual(CARRIER_FALLBACKS, [])

    def test_without_fallbacks_the_rejection_is_propagated_once(self):
        from dropi_client import DropiAPIError

        from orders.services import create_order_with_carrier_fallback

        client = self._client(DropiAPIError(self.CITY_ERROR))
        with self.assertRaises(DropiAPIError):
            create_order_with_carrier_fallback(client, {"shop_order_id": 1})
        self.assertEqual(client.create_order.call_count, 1)

    def _client(self, side_effect):
        from unittest.mock import MagicMock

        client = MagicMock()
        client.create_order.side_effect = side_effect
        return client

    @patch("orders.services.CARRIER_FALLBACKS", SAMPLE_CARRIERS)
    def test_retries_with_other_carrier_and_succeeds(self):
        from dropi_client import DropiAPIError

        from orders.services import create_order_with_carrier_fallback

        calls = []

        def side_effect(payload):
            calls.append(payload.get("distribution_company_id"))
            if payload.get("distribution_company_id") is None:
                raise DropiAPIError(self.CITY_ERROR)
            return {"objects": {"id": 123}}

        response = create_order_with_carrier_fallback(self._client(side_effect), {"shop_order_id": 1})
        self.assertEqual(response["objects"]["id"], 123)
        self.assertEqual(calls, [None, 2])  # predeterminada → Envía

    def test_other_errors_are_not_retried(self):
        from dropi_client import DropiAPIError

        from orders.services import create_order_with_carrier_fallback

        client = self._client(DropiAPIError("El producto actualmente lo clasifica el proveedor como archivado"))
        with self.assertRaises(DropiAPIError):
            create_order_with_carrier_fallback(client, {"shop_order_id": 1})
        self.assertEqual(client.create_order.call_count, 1)

    @patch("orders.services.CARRIER_FALLBACKS", SAMPLE_CARRIERS)
    def test_all_carriers_fail_raises_last_error(self):
        from dropi_client import DropiAPIError

        from orders.services import create_order_with_carrier_fallback

        client = self._client(DropiAPIError(self.CITY_ERROR))
        with self.assertRaises(DropiAPIError):
            create_order_with_carrier_fallback(client, {"shop_order_id": 1})
        self.assertEqual(client.create_order.call_count, 1 + 3)


class FoldShippingIntoPricesTests(SimpleTestCase):
    def test_pedido_100_two_units_carry_the_shipping(self):
        from orders.services import fold_shipping_into_prices

        products = [{"price": 15900, "quantity": 2}]
        fold_shipping_into_prices(products, 63800)
        self.assertEqual(products[0]["price"], 31900)

    def test_shipping_goes_to_the_single_unit_line(self):
        from orders.services import fold_shipping_into_prices

        products = [{"price": 20000, "quantity": 3}, {"price": 10000, "quantity": 1}]
        fold_shipping_into_prices(products, 70000 + 12345)
        self.assertEqual(products, [{"price": 20000, "quantity": 3}, {"price": 22345, "quantity": 1}])


class CheckoutDoesNotLoseSalesTests(TestCase):
    """Lección de Colombia (octubre 2026): dos ventas se perdieron en el
    formulario y nadie se enteró. El formulario corrige lo corregible, explica
    lo demás y cada intento fallido queda en CheckoutAttempt."""

    DETAIL = {"objects": {
        "id": 2098624, "active": True, "privated_product": False, "suggested_price": "300.00", "variations": [],
        "warehouse_product": [{"warehouse_id": 13341, "stock": 37157}],
    }}

    def setUp(self):
        caches["ratelimit"].clear()  # límite de checkouts por IP (django-ratelimit)
        cat = Category.objects.create(name="Bienestar íntimo", dropi_id="store:bienestar_intimo")
        self.product = Product.objects.create(
            dropi_id=2098624, supplier_id=205895, name="Vigormax", slug="vigormax", price=Decimal("349"),
            cost=Decimal("170"), suggested_price=Decimal("300"), stock=37173, category=cat, is_active=True,
            images=["https://x/1.jpg"],
        )
        self.base = {"name": "Jose", "surname": "Rojas", "email": "", "phone": "5512345678",
                     "address": "Av. Juárez 123, col. Centro", "state": "CMX", "city": "Cuauhtémoc",
                     "zip_code": "99999", "payment_method": Order.PAYMENT_COD}

    def _add_to_cart(self):
        r = self.client.post(f"/carrito/agregar/{self.product.pk}/", {"quantity": 1},
                             HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 200)

    def _checkout(self, mock_cls, **override):
        mock_cls.return_value.get_product.return_value = self.DETAIL
        mock_cls.return_value.create_order.return_value = {"objects": {"id": 555}}
        self._add_to_cart()
        return self.client.post(reverse("orders:checkout"), {**self.base, **override})

    @patch("orders.views.DropiClient")
    def test_city_with_wrong_state_is_corrected_not_rejected(self, mock_cls):
        r = self._checkout(mock_cls, state="MEX", city="Guadalajara")
        self.assertEqual(r.status_code, 302)
        order = Order.objects.get()
        self.assertEqual((order.state, order.city), ("JAL", "Guadalajara"))

    @patch("orders.views.DropiClient")
    def test_city_known_only_by_zip_is_completed(self, mock_cls):
        r = self._checkout(mock_cls, state="", city="", zip_code="06600")
        self.assertEqual(r.status_code, 302)
        order = Order.objects.get()
        self.assertEqual((order.state, order.city, order.zip_code), ("CMX", "Cuauhtémoc", "06600"))

    @patch("orders.views.DropiClient")
    def test_phone_written_with_spaces_or_country_code_is_accepted(self, mock_cls):
        for phone in ("55 1234 5678", "+52 55 1234 5678", "+52 1 55 1234 5678", "55-1234-5678",
                      "(55) 12345678", "044 55 1234 5678"):
            with self.subTest(phone=phone):
                caches["ratelimit"].clear()  # límite de 20 checkouts/hora por IP (django-ratelimit)
                Order.objects.all().delete()
                r = self._checkout(mock_cls, phone=phone)
                self.assertEqual(r.status_code, 302, phone)
                self.assertEqual(Order.objects.get().phone, "5512345678")

    def test_form_fixes_what_it_can(self):
        form = CheckoutForm(data={**self.base, "surname": "", "name": "Ana María López Gómez",
                                  "email": "ana@gmail", "city": "gustavo a madero"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual((form.cleaned_data["name"], form.cleaned_data["surname"]), ("Ana María", "López Gómez"))
        self.assertEqual(form.cleaned_data["email"], "")  # opcional y mal escrito: no bloquea la compra
        self.assertEqual(form.cleaned_data["city"], "Gustavo A. Madero")

    def test_ambiguous_city_asks_for_the_department(self):
        # Hay un Abasolo en Coahuila, Guanajuato, Nuevo León y Tamaulipas.
        form = CheckoutForm(data={**self.base, "state": "AGU", "city": "Abasolo"})
        self.assertFalse(form.is_valid())
        self.assertIn("Elige el estado correcto", form.errors["state"][0])

    def test_states_are_listed_in_alphabetical_order(self):
        from cart.mexico_geo import norm

        from .forms import COLOMBIA_DEPARTMENTS

        labels = [label for code, label in COLOMBIA_DEPARTMENTS if code]
        self.assertEqual(len(labels), 32)
        self.assertEqual(labels, sorted(labels, key=norm))
        self.assertIn("Ciudad de México", labels)

    @patch("orders.views.DropiClient")
    def test_failed_attempt_is_recorded_and_linked_when_customer_retries(self, mock_cls):
        from .models import CheckoutAttempt

        r = self._checkout(mock_cls, phone="551234")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Revisa este dato para confirmar tu pedido")
        attempt = CheckoutAttempt.objects.get()
        self.assertEqual(attempt.stage, CheckoutAttempt.STAGE_VALIDATION)
        self.assertIn("phone", attempt.errors)
        self.assertEqual(attempt.data["name"], "Jose")
        self.assertEqual(attempt.cart[0]["name"], "Vigormax")

        r = self.client.post(reverse("orders:checkout"), self.base)
        self.assertEqual(r.status_code, 302)
        attempt.refresh_from_db()
        self.assertEqual(attempt.order, Order.objects.get())

    @patch("orders.views.DropiClient")
    def test_unexpected_error_keeps_form_and_unblocks_retry(self, mock_cls):
        from .models import CheckoutAttempt

        mock_cls.return_value.get_product.return_value = self.DETAIL
        self._add_to_cart()
        with patch("orders.views.fold_shipping_into_prices", side_effect=RuntimeError("boom")):
            r = self.client.post(reverse("orders:checkout"), self.base)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "problema nuestro")
        self.assertEqual(CheckoutAttempt.objects.get().stage, CheckoutAttempt.STAGE_ERROR)
        self.assertNotIn("checkout_submitting", self.client.session)

    def test_stale_submitting_flag_does_not_block(self):
        self._add_to_cart()
        session = self.client.session
        session["checkout_submitting"] = True  # marca vieja de antes del cambio
        session.save()
        with patch("orders.views.DropiClient") as mock_cls:
            mock_cls.return_value.get_product.return_value = self.DETAIL
            mock_cls.return_value.create_order.return_value = {"objects": {"id": 1}}
            r = self.client.post(reverse("orders:checkout"), self.base)
        self.assertEqual(r.status_code, 302)

    def test_attempt_blocked_in_browser_is_recorded(self):
        import json as _json

        from .models import CheckoutAttempt

        self._add_to_cart()
        r = self.client.post(reverse("orders:checkout_attempt"), {
            **self.base, "phone": "55 12", "try": "2",
            "errors": _json.dumps({"phone": "Tiene 4 dígitos y un celular en México tiene 10."}),
        })
        self.assertEqual(r.status_code, 200)
        attempt = CheckoutAttempt.objects.get()
        self.assertEqual(attempt.data["phone"], "55 12")
        self.assertIn("phone", attempt.errors)
        self.assertIn("navegador", attempt.detail)
        self.assertEqual(attempt.cart[0]["name"], "Vigormax")

    def test_phone_with_old_mobile_prefix_is_accepted(self):
        form = CheckoutForm(data={**self.base, "phone": "045 33 1234 5678"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "3312345678")
