import json
import re
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from .models import Category, Product


class ShippingDisplayTests(TestCase):
    """Sin ciudad, la ficha no muestra un envío como si fuera el del cliente;
    la tarjeta solo promete "Envío gratis" si el margen cubre la guía más cara
    en uso; el JSON-LD no declara una tarifa fija."""

    def setUp(self):
        cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        # margen 139 < guía (188) + piso (55): no es envío gratis; el cobro
        # (188 + 55 − 139 = 104) queda bajo el techo, así que no pide combo.
        self.cheap = Product.objects.create(
            dropi_id=1, name="Crema depilatoria", slug="crema", category=cat,
            price=Decimal("199"), cost=Decimal("60"), stock=5, is_active=True,
        )

    def test_pdp_without_city_asks_for_city(self):
        html = self.client.get("/producto/crema/").content.decode()
        self.assertIn("Elige tu ciudad para ver el costo del envío", html)
        self.assertIn("Llega en 1 a 5 días hábiles · elige tu ciudad para ver la fecha", html)
        self.assertIn('id="pdp-city-input"', html)
        self.assertNotIn("<option", html.split('id="pdp-city-input"')[1].split("</div>")[0])
        self.assertNotIn(f"${settings.SHIPPING_ZONE_B_COST}", html)  # envío de zona B por defecto

    def test_pdp_with_city_shows_real_shipping(self):
        session = self.client.session
        session["visitor_city"] = {"city": "Guadalajara", "state": "Jalisco"}
        session.save()
        html = self.client.get("/producto/crema/").content.decode()
        self.assertNotIn("Elige tu ciudad para ver el envío", html)
        self.assertIn('id="pdp-shipping-cost"', html)
        self.assertIn('value="Guadalajara"', html)
        self.assertIn("Llega entre el", html)

    def test_free_shipping_badge_requires_costliest_zone_in_use(self):
        from cart.shipping import max_guide_cost
        from catalog.services.pricing import min_gain

        cost = Decimal("200")
        keep = min_gain(cost)
        zone_a, top = settings.SHIPPING_ZONE_A_COST, max_guide_cost()
        self.assertGreaterEqual(top, zone_a)
        if top > zone_a:
            p = Product(price=cost + zone_a + keep + 10, cost=cost)
            self.assertFalse(p.likely_free_shipping)  # cubre zona A pero no la más cara
        p = Product(price=cost + top, cost=cost)
        self.assertFalse(p.likely_free_shipping)  # cubre la guía pero no la ganancia mínima
        p = Product(price=cost + top + keep, cost=cost)
        self.assertTrue(p.likely_free_shipping)

    def test_empty_zone_c_does_not_hide_free_shipping(self):
        # Ningún municipio está en zona C: exigir su guía (más cara) le quitaba
        # el sello a productos que en ningún municipio cobran envío.
        from cart.shipping import calc_shipping, max_guide_cost, zones_in_use
        from catalog.services.pricing import min_gain

        self.assertNotIn("C", zones_in_use())
        self.assertEqual(max_guide_cost(), settings.SHIPPING_ZONE_B_COST)
        cost = Decimal("200")
        p = Product(price=cost + settings.SHIPPING_ZONE_B_COST + min_gain(cost), cost=cost)
        self.assertTrue(p.likely_free_shipping)
        line = {"price": p.price, "cost": p.cost, "quantity": 1, "supplier_id": 1}
        for city in ("Guadalajara", "Tepic", "Municipio que no está en la lista"):
            self.assertEqual(calc_shipping([line], city)["total_shipping"], 0, city)

    def test_json_ld_has_no_fixed_shipping_rate(self):
        html = self.client.get("/producto/crema/").content.decode()
        ld = json.loads(re.search(r'(?s)<script type="application/ld\+json">(.*?)</script>', html).group(1))
        product = next(item for item in ld["@graph"] if item["@type"] == "Product")
        # El envío depende de la ciudad: solo se declara cuando es gratis en todas.
        self.assertNotIn("shippingDetails", product["offers"])
        self.assertEqual(product["offers"]["priceCurrency"], "MXN")


class MainlandFreeShippingJsonLdTests(SimpleTestCase):
    def test_all_states_are_mainland_while_zone_c_is_empty(self):
        from catalog.seo import mainland_regions

        regions = mainland_regions()
        self.assertEqual(len(regions), 32)
        self.assertIn("CMX", regions)
        self.assertIn("JAL", regions)

    def test_free_shipping_declared_only_where_checkout_charges_nothing(self):
        # Con un destino en zona C, la regla de Colombia vuelve a aplicar:
        # gratis hasta la B se declara solo en los estados sin zona C.
        from cart import shipping
        from catalog.seo import free_shipping_outside_remote_zones, mainland_regions
        from catalog.services.pricing import min_gain

        remote = [*shipping.MEXICO_CITIES, ("Cozumel", "ROO", "C")]
        with mock.patch.object(shipping, "MEXICO_CITIES", remote), \
                mock.patch.dict(shipping._CITY_ZONE_MAP, {"cozumel": "C"}):
            cost = Decimal("200")
            keep = min_gain(cost)
            p = Product(price=cost + settings.SHIPPING_ZONE_B_COST + keep, cost=cost)
            self.assertTrue(free_shipping_outside_remote_zones(p))
            self.assertFalse(p.likely_free_shipping)  # en la zona remota sí se cobra
            line = {"price": p.price, "cost": p.cost, "quantity": 1, "supplier_id": 1}
            for city in ("Guadalajara", "Tepic"):
                self.assertEqual(shipping.calc_shipping([line], city)["total_shipping"], 0, city)
            self.assertGreater(shipping.calc_shipping([line], "Cozumel")["total_shipping"], 0)
            self.assertNotIn("ROO", mainland_regions())

            p = Product(price=cost + settings.SHIPPING_ZONE_B_COST + keep - 10, cost=cost)
            self.assertFalse(free_shipping_outside_remote_zones(p))


class FeedShippingTests(TestCase):
    """El feed de Merchant declara el mismo envío que cobra el checkout por
    una unidad, mientras la guía cueste lo mismo en todo el país."""

    def setUp(self):
        cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        self.paid = Product.objects.create(
            dropi_id=1, name="Crema depilatoria", slug="crema", category=cat,
            price=Decimal("199"), cost=Decimal("60"), stock=5, is_active=True,
        )
        self.free = Product.objects.create(
            dropi_id=2, name="Secadora", slug="secadora", category=cat,
            price=Decimal("899"), cost=Decimal("300"), stock=5, is_active=True,
        )

    def test_feed_shipping_matches_checkout(self):
        from cart.shipping import calc_shipping
        from catalog.feeds import feed_shipping_price

        for product in (self.paid, self.free):
            line = {"price": product.price, "cost": product.cost, "quantity": 1, "supplier_id": 7}
            charged = calc_shipping([line], "Guadalajara")["total_shipping"]
            self.assertEqual(feed_shipping_price(product), charged)
        self.assertEqual(feed_shipping_price(self.free), Decimal("0"))
        self.assertGreater(feed_shipping_price(self.paid), 0)

    def test_feed_declares_only_free_shipping_when_zones_differ(self):
        from catalog.feeds import feed_shipping_price

        with self.settings(SHIPPING_ZONE_A_COST=150):
            self.assertIsNone(feed_shipping_price(self.paid))
            self.assertEqual(feed_shipping_price(self.free), Decimal("0"))
