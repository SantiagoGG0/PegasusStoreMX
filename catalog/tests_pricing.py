import re
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from catalog.models import Category, Product
from catalog.services.dropi_import import upsert_product
from catalog.services.gallery_sync import fetch_gallery
from catalog.services.pricing import (
    STATUS_FREE_SHIPPING,
    STATUS_LOW_MARGIN,
    STATUS_NO_COST,
    STATUS_PAID_SHIPPING,
    charm_round,
    compute_price,
    delivered_profit,
    expected_net_profit,
    min_gain,
    min_gain_expression,
    shipping_charged,
)
from catalog.services.ranking import compute_rank_score
from cart.shipping import calc_shipping

# Valores de México (MXN), ver config/settings.py.
PRICING = dict(
    SHIPPING_ZONE_A_COST=120,
    COD_REJECTION_RATE=0.25,
    COD_REJECTION_LOSS=120,
    PRICING_MIN_GAIN_LADDER=[
        (50, 35, 1.00),
        (120, 55, 0),
        (250, 85, 0),
        (500, 120, 0),
        (None, 120, 0.15),
    ],
    PRICING_MAX_OVER_SUGGESTED=1.3,
    PRICING_EXPENSIVE_FROM=500,
    PRICING_MAX_OVER_SUGGESTED_EXPENSIVE=1.1,
    PRICING_DEFAULT_PROFILE={"markup": 1.8, "weight": 1.0},
    PRICING_CATEGORY_PROFILES={"belleza": {"markup": 2.0, "weight": 1.5}},
    # Regla base (techo solo por sugerido); la absorción de la guía se prueba aparte.
    PRICING_MAX_COST_MULTIPLE=0,
    PRICING_TARGET_SHIPPING=120,
)

# México: techo de 3× el costo y envío objetivo de $99 con guía de $188.
ABSORB = {**PRICING, "SHIPPING_ZONE_A_COST": 188, "COD_REJECTION_LOSS": 188,
          "PRICING_MAX_COST_MULTIPLE": 3.0, "PRICING_TARGET_SHIPPING": 99}


@override_settings(**ABSORB)
class ShippingAbsorptionTests(SimpleTestCase):
    """El sugerido de Dropi México está casi pegado al costo: el precio sube
    para absorber la guía y el envío visible baja, sin bajar la ganancia."""

    def _check(self, cost, suggested):
        decision = compute_price(cost, suggested, "store:otros")
        margin, keep = decision.price - cost, min_gain(cost)
        charged = shipping_charged(margin, 188, keep)
        return decision, charged, delivered_profit(margin, keep, 188)

    def test_price_absorbs_guide_down_to_target_shipping(self):
        # costo 127, piso 85: 127 + 85 + (188 − 99) = 301 → $309; envío 188 + 85 − 182 = 91
        decision, charged, profit = self._check(127, 174)
        self.assertEqual(decision.price, Decimal("309"))
        self.assertEqual(charged, Decimal("91"))
        self.assertLessEqual(charged, 99)
        self.assertEqual(profit, Decimal("85"))  # nunca menos que el piso

    def test_free_shipping_when_cost_cap_allows_it(self):
        # costo 200: 200 + 188 + 85 = 473 ≤ 600 (3× costo) → $479, envío gratis
        decision, charged, profit = self._check(200, 280)
        self.assertEqual((decision.price, decision.status), (Decimal("479"), STATUS_FREE_SHIPPING))
        self.assertEqual(charged, Decimal("0"))
        self.assertEqual(profit, Decimal("91"))

    def test_cheap_product_absorbs_as_much_as_the_cap_allows(self):
        # costo 45: tope 135 → $139; el envío baja de 188 a 139 y la ganancia se mantiene
        decision, charged, profit = self._check(45, 55)
        self.assertEqual(decision.price, Decimal("139"))
        self.assertEqual(charged, Decimal("139"))
        self.assertEqual(profit, Decimal("45"))

    def _old(self, cost, suggested):
        with self.settings(PRICING_MAX_COST_MULTIPLE=0):
            old = compute_price(cost, suggested, "store:otros")
        margin, keep = old.price - cost, min_gain(cost)
        return old, shipping_charged(margin, 188, keep), delivered_profit(margin, keep, 188)

    def test_customer_total_does_not_change_only_the_split(self):
        decision, charged, profit = self._check(127, 174)
        old, old_charged, old_profit = self._old(127, 174)
        # mismo total salvo el redondeo a ...9; menos envío visible, misma ganancia
        self.assertLess(abs((decision.price + charged) - (old.price + old_charged)), 10)
        self.assertLess(charged, old_charged)
        self.assertEqual(profit, old_profit)

    def test_store_never_earns_less_than_before(self):
        for cost, suggested in ((45, 55), (127, 174), (200, 280), (500, 650)):
            with self.subTest(cost=cost):
                _, charged, profit = self._check(cost, suggested)
                _, old_charged, old_profit = self._old(cost, suggested)
                self.assertGreaterEqual(profit, old_profit)
                self.assertLessEqual(charged, old_charged)


@override_settings(**PRICING)
class PricingTests(SimpleTestCase):
    def test_charm_round_ends_in_9(self):
        # Hasta $999 de 10 en 10; desde $1,000 de 100 en 100.
        self.assertEqual(charm_round(Decimal("127")), Decimal("129"))
        self.assertEqual(charm_round(Decimal("129")), Decimal("129"))
        self.assertEqual(charm_round(Decimal("130")), Decimal("139"))
        self.assertEqual(charm_round(Decimal("990")), Decimal("999"))
        self.assertEqual(charm_round(Decimal("999")), Decimal("999"))
        self.assertEqual(charm_round(Decimal("1000")), Decimal("1099"))
        self.assertEqual(charm_round(Decimal("1234")), Decimal("1299"))

    def test_charm_round_never_jumps_a_cheap_product_to_900(self):
        # Con el redondeo de Colombia (a ...900 por cada mil) $127 quedaba en $900.
        self.assertLess(charm_round(Decimal("127")), Decimal("140"))

    def test_min_gain_ladder(self):
        self.assertEqual(min_gain(30), Decimal("35"))       # mínimo $35
        self.assertEqual(min_gain(40), Decimal("40"))       # al menos el costo
        self.assertEqual(min_gain(100), Decimal("55"))
        self.assertEqual(min_gain(200), Decimal("85"))
        self.assertEqual(min_gain(400), Decimal("120"))
        self.assertEqual(min_gain(3000), Decimal("450"))    # 15% del costo
        self.assertEqual(min_gain(0), Decimal("0"))

    def test_shipping_charged_keeps_store_gain(self):
        self.assertEqual(shipping_charged(250, 120, 85), Decimal("0"))     # envío gratis
        self.assertEqual(shipping_charged(150, 120, 85), Decimal("55"))    # paga una parte
        self.assertEqual(shipping_charged(20, 120, 35), Decimal("120"))    # paga la guía completa
        self.assertEqual(delivered_profit(150, 85), Decimal("85"))
        self.assertEqual(delivered_profit(20, 35), Decimal("20"))
        self.assertEqual(expected_net_profit(150, 85), Decimal("33.75"))   # 0.75 × 85 − 0.25 × 120

    def test_keep_zero_is_previous_behaviour(self):
        self.assertEqual(shipping_charged(70, 120, 0), Decimal("50"))
        self.assertEqual(shipping_charged(150, 120, 0), Decimal("0"))

    def test_cheap_product_keeps_its_cost_as_gain(self):
        # costo $40, sugerido $90: no alcanza para envío gratis, el cliente paga envío
        decision = compute_price(40, 90, "store:otros")
        self.assertEqual((decision.price, decision.status), (Decimal("99"), STATUS_PAID_SHIPPING))
        self.assertEqual(delivered_profit(decision.price - 40, min_gain(40)), Decimal("40"))

    def test_high_perceived_value_follows_market(self):
        # costo $90, sugerido $399: precio de mercado, envío gratis, ganancia >> piso
        decision = compute_price(90, 399, "store:otros")
        self.assertEqual((decision.price, decision.status), (Decimal("399"), STATUS_FREE_SHIPPING))

    def test_low_margin_is_not_priced_out_of_market(self):
        # tope 160 × 1.3 = 208 → $209; ni el piso pagado (235) cabe
        decision = compute_price(150, 160, "store:otros")
        self.assertEqual((decision.price, decision.status), (Decimal("209"), STATUS_LOW_MARGIN))

    def test_expensive_products_have_tighter_market_cap(self):
        # tope 1,300 × 1.1 = 1,430 (no 1.3 → 1,690) → $1,499
        decision = compute_price(1000, 1300, "store:otros")
        self.assertEqual((decision.price, decision.status), (Decimal("1499"), STATUS_FREE_SHIPPING))

    def test_suggested_below_cost_is_ignored(self):
        # Sugerido de $1 mal cargado por el proveedor.
        decision = compute_price(45, 1, "store:otros")
        self.assertEqual(decision.price, compute_price(45, 0, "store:otros").price)
        self.assertGreater(decision.price, Decimal("45"))

    def test_no_cost(self):
        decision = compute_price(0, 450)
        self.assertEqual(decision.status, STATUS_NO_COST)
        self.assertEqual(decision.price, Decimal("459"))

    def test_checkout_charges_hybrid_shipping_per_supplier(self):
        # proveedor 1: margen 99, piso 85 → paga 106; proveedor 2: margen 249 → gratis
        lines = [
            {"price": "249", "cost": "150", "quantity": 1, "supplier_id": 1},
            {"price": "399", "cost": "150", "quantity": 1, "supplier_id": 2},
        ]
        with mock.patch("cart.shipping.get_zone", return_value={"zone": "A", "guide_cost": 120}):
            result = calc_shipping(lines, "Guadalajara")
        self.assertEqual(result["total_shipping"], Decimal("106"))


@override_settings(**PRICING)
class MinGainExpressionTests(TestCase):
    def test_orm_expression_matches_python(self):
        cat = Category.objects.create(dropi_id="store:otros", name="Otros")
        for i, cost in enumerate((30, 40, 100, 200, 400, 3000)):
            Product.objects.create(dropi_id=i + 1, name=f"P{i}", slug=f"p{i}", category=cat, cost=cost, price=cost * 2)
        for product in Product.objects.annotate(gain=min_gain_expression()):
            self.assertEqual(Decimal(product.gain).quantize(Decimal("1")), min_gain(product.cost))


@override_settings(**PRICING, CATALOG_MIN_IMAGES=2)
class RankingTests(TestCase):
    def _product(self, **kwargs):
        cat, _ = Category.objects.get_or_create(dropi_id=kwargs.pop("cat", "store:belleza"), defaults={"name": "Belleza"})
        defaults = dict(
            dropi_id=kwargs.pop("dropi_id", 1), name="P", slug=f"p-{kwargs.get('stock', 0)}-{len(kwargs)}",
            category=cat, cost=Decimal("150"), price=Decimal("499"), stock=100,
            images=[{"url": f"https://x/{i}.jpg"} for i in range(5)], description="x" * 300,
        )
        defaults.update(kwargs)
        return Product(**defaults)

    def test_score_is_bounded_and_rewards_quality(self):
        good = compute_rank_score(self._product())
        one_image = compute_rank_score(self._product(images=[{"url": "https://x/1.jpg"}]))
        low_margin = compute_rank_score(self._product(pricing_status=STATUS_LOW_MARGIN))
        self.assertTrue(0 <= one_image < good <= 100)
        self.assertLess(low_margin, good)

    def test_priority_category_ranks_higher(self):
        other = compute_rank_score(self._product(cat="store:otros"))
        self.assertLess(other, compute_rank_score(self._product()))


class GalleryTests(TestCase):
    RAW = {
        "id": 77, "name": "Serum", "sale_price": 20000, "suggested_price": 50000,
        "gallery": [{"urlS3": "mexico/products/77/a.jpg"}], "warehouse_product": [{"stock": 9}],
    }

    def test_listing_import_does_not_overwrite_synced_gallery(self):
        product, _ = upsert_product(self.RAW)
        gallery = [{"url": f"https://cdn/{i}.jpg"} for i in range(4)]
        Product.objects.filter(pk=product.pk).update(images=gallery, gallery_synced_at=timezone.now())

        product, _ = upsert_product(self.RAW)
        product.refresh_from_db()
        self.assertEqual(product.images, gallery)
        self.assertEqual(product.suggested_price, Decimal("50000"))

    def test_product_dropi_cannot_return_is_not_retried(self):
        from dropi_client import DropiAPIError

        client = mock.Mock()
        client.get_product.side_effect = DropiAPIError("Ha ocurrido un error al obtener el producto")
        with mock.patch("catalog.services.gallery_sync.time.sleep") as sleep:
            result = fetch_gallery(client, mock.Mock(), 77)
        self.assertFalse(result.found)
        self.assertEqual(client.get_product.call_count, 1)
        sleep.assert_not_called()

    def test_fetch_gallery_drops_broken_images(self):
        client = mock.Mock()
        client.get_product.return_value = {"objects": {
            "active": True, "sale_price": 20000, "suggested_price": 50000,
            "photos": [{"urlS3": "a.jpg"}, {"urlS3": "b.jpg"}, {"urlS3": "a.jpg"}],
            "warehouse_product": [{"stock": 4}],
        }}
        session = mock.Mock()
        # Las fotos se verifican en paralelo: la respuesta depende de la URL, no del orden.
        session.head.side_effect = lambda url, **kw: (
            mock.Mock(status_code=200, headers={"Content-Type": "image/jpeg"}) if url.endswith("a.jpg")
            else mock.Mock(status_code=403, headers={})
        )
        result = fetch_gallery(client, session, 77)
        self.assertEqual([i["url"].rsplit("/", 1)[-1] for i in result.images], ["a.jpg"])
        self.assertEqual((result.broken, result.stock, result.suggested), (1, 4, Decimal("50000")))


class GalleryOnViewTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(dropi_id="store:otros", name="Otros")
        self.product = Product.objects.create(
            dropi_id=55, name="Serum", slug="serum", category=cat, cost=10_000, price=40_000,
            stock=5, is_active=True, images=[{"url": "https://cdn/a.jpg"}],
        )
        from django.core.cache import cache
        cache.clear()

    def _detail(self, *names):
        return {"objects": {"photos": [{"url": f"https://cdn/{n}"} for n in names]}}

    @override_settings(GALLERY_ON_VIEW=True, GALLERY_ON_VIEW_ASYNC=False)
    def test_product_page_fetches_full_gallery_once(self):
        with mock.patch("catalog.services.gallery_sync.DropiClient") as client:
            client.return_value.get_product.return_value = self._detail("a.jpg", "b.jpg", "c.jpg")
            html = self.client.get("/producto/serum/").content.decode()
            self.client.get("/producto/serum/")
        self.assertEqual(client.return_value.get_product.call_count, 1)
        self.product.refresh_from_db()
        self.assertEqual(len(self.product.images), 3)
        self.assertIn("cdn%2Fc.jpg", html)

    @override_settings(GALLERY_ON_VIEW=True, GALLERY_ON_VIEW_ASYNC=False)
    def test_dropi_error_keeps_existing_images(self):
        with mock.patch("catalog.services.gallery_sync.DropiClient") as client:
            client.return_value.get_product.side_effect = Exception("429 Too Many Requests")
            response = self.client.get("/producto/serum/")
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.images, [{"url": "https://cdn/a.jpg"}])

    @override_settings(GALLERY_ON_VIEW=True, GALLERY_ON_VIEW_ASYNC=False)
    def test_bots_do_not_spend_dropi_quota(self):
        with mock.patch("catalog.services.gallery_sync.DropiClient") as client:
            self.client.get("/producto/serum/", HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)")
        client.return_value.get_product.assert_not_called()


class SeoTextTests(SimpleTestCase):
    def test_clean_meta_description_without_emojis_or_boilerplate(self):
        from types import SimpleNamespace

        from catalog.seo import generate_meta_description, generate_seo_title

        product = SimpleNamespace(
            name="ACEITE DE JENGIBRE X1", price=Decimal("399"), meta_title="", meta_description="",
            description_unique="", likely_free_shipping=True,
            description="<p>🫚 ACEITE DE JENGIBRE – TERAPIA 🌿🔥</p>\nDescripción del producto: Activa tu bienestar.",
        )
        description = generate_meta_description(product)
        self.assertTrue(description.startswith("Aceite de jengibre x1 por $399, con pago contra entrega y envío gratis"))
        self.assertNotIn("🫚", description)
        self.assertNotIn("Descripción del producto", description)
        self.assertLessEqual(len(description), 155)
        self.assertEqual(generate_seo_title(product), "Aceite de jengibre x1 | Pago contra entrega | Pegasus Store")

    def test_category_copy_fits_search_snippets(self):
        from catalog.seo_content import CATEGORY_SEO

        for key, copy in CATEGORY_SEO.items():
            with self.subTest(category=key):
                self.assertLessEqual(len(copy["description"]), 155)
                self.assertTrue(copy["intro"])



class CatalogPaginationSeoTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        for i in range(60):
            Product.objects.create(
                dropi_id=1000 + i, name=f"Producto {i}", slug=f"producto-{i}", category=cat,
                cost=Decimal("10000"), price=Decimal("40000"), stock=5, is_active=True,
            )

    def test_page_two_is_real_crawlable_and_stable(self):
        bot = {"HTTP_USER_AGENT": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
        first = self.client.get("/categoria/belleza/", **bot).content.decode()
        page2 = self.client.get("/categoria/belleza/?page=2", **bot)
        html = page2.content.decode()
        self.assertEqual(page2.status_code, 200)
        self.assertIn('rel="next"', first)
        self.assertIn('rel="prev"', html)
        self.assertIn('<link rel="canonical" href="http://testserver/categoria/belleza/?page=2"', html)  # canonical propio
        again = self.client.get("/categoria/belleza/?page=2", **bot).content.decode()
        slugs = lambda h: re.findall(r'href="/producto/([^/]+)/"', h)
        self.assertEqual(slugs(html), slugs(again))           # mismo orden en cada visita
        self.assertFalse(set(slugs(html)) & set(slugs(first)))  # la página 2 no repite la 1

    def test_page_beyond_last_is_404(self):
        self.assertEqual(self.client.get("/categoria/belleza/?page=99").status_code, 404)

    def test_old_category_url_redirects_permanently(self):
        response = self.client.get("/?category=store:belleza&page=2&sort=price_asc")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/categoria/belleza/?page=2&sort=price_asc")

    def test_unknown_category_slug_is_404(self):
        self.assertEqual(self.client.get("/categoria/no-existe/").status_code, 404)

    def test_infinite_scroll_keeps_the_category(self):
        html = self.client.get("/categoria/belleza/").content.decode()
        self.assertIn('data-category="store:belleza"', html)


class GoogleMerchantFeedTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        base = dict(category=cat, cost=Decimal("10000"), stock=5, is_active=True)
        self.free = Product.objects.create(
            dropi_id=1, name="SERUM 🔥", slug="serum", price=Decimal("90000"),
            images=[{"url": "https://cdn/a.jpg"}, {"url": "https://cdn/b.jpg"}], **base,
        )
        Product.objects.create(dropi_id=2, name="Sin fotos", slug="sin-fotos", price=Decimal("50000"), images=[], **base)
        Product.objects.create(dropi_id=3, name="Excluido", slug="excluido", price=Decimal("50000"),
                               images=[{"url": "https://cdn/c.jpg"}], seo_exclusion="e", **base)
        base["is_active"] = False
        Product.objects.create(dropi_id=4, name="Inactivo", slug="inactivo", price=Decimal("50000"),
                               images=[{"url": "https://cdn/d.jpg"}], **base)

    def test_feed_lists_only_sellable_products_with_full_data(self):
        import tempfile
        import xml.etree.ElementTree as ET
        from pathlib import Path

        from django.test import RequestFactory

        from catalog import feeds

        path = Path(tempfile.mkdtemp()) / "feed.xml"
        feeds.write_feed(RequestFactory().get("/"), path)
        with mock.patch.object(feeds, "FEED_FILE", path):
            response = self.client.get("/feeds/google-merchant.xml")   # archivo fresco: se sirve tal cual
        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(b"".join(response.streaming_content))
        ns = {"g": "http://base.google.com/ns/1.0"}
        items = root.findall("channel/item")
        self.assertEqual([i.find("g:id", ns).text for i in items], ["1"])
        item = items[0]
        self.assertEqual(item.find("title").text, "Serum")
        self.assertEqual(item.find("g:price", ns).text, "90000.00 MXN")
        self.assertEqual(item.find("g:image_link", ns).text, "https://cdn/a.jpg")
        self.assertEqual([e.text for e in item.findall("g:additional_image_link", ns)], ["https://cdn/b.jpg"])
        self.assertEqual(item.find("g:shipping/g:price", ns).text, "0.00 MXN")   # envío gratis en todo el país

    def test_feed_missing_is_generated_in_background_and_503_meanwhile(self):
        import tempfile
        from pathlib import Path

        from catalog import feeds

        path = Path(tempfile.mkdtemp()) / "feed.xml"
        with mock.patch.object(feeds, "FEED_FILE", path),              mock.patch.object(feeds, "_regenerate_in_background") as regenerate:
            response = self.client.get("/feeds/google-merchant.xml")
        self.assertEqual(response.status_code, 503)
        regenerate.assert_called_once()


class GalleryOnViewAsyncTests(TestCase):
    @override_settings(GALLERY_ON_VIEW=True, GALLERY_ON_VIEW_ASYNC=True)
    def test_product_page_does_not_wait_for_dropi(self):
        from django.core.cache import cache

        cache.clear()
        cat = Category.objects.create(dropi_id="store:otros", name="Otros")
        Product.objects.create(dropi_id=56, name="Crema", slug="crema-async", category=cat, cost=10_000,
                               price=40_000, stock=5, is_active=True, images=[{"url": "https://cdn/a.jpg"}])
        with mock.patch("catalog.services.gallery_sync.threading.Thread") as thread:
            response = self.client.get("/producto/crema-async/")
        self.assertEqual(response.status_code, 200)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()



class SeoUrlAndSnippetTests(SimpleTestCase):
    def test_image_urls_with_spaces_are_encoded(self):
        from catalog.seo import encode_url

        self.assertEqual(
            encode_url("https://cdn.example/colombia/products/1/WhatsApp Image 2025 at 5.03 PM.jpeg"),
            "https://cdn.example/colombia/products/1/WhatsApp%20Image%202025%20at%205.03%20PM.jpeg",
        )
        self.assertEqual(encode_url("https://cdn.example/a%20b.jpg"), "https://cdn.example/a%20b.jpg")  # no doble codificación

    def test_uppercase_heading_is_not_repeated_in_description(self):
        from types import SimpleNamespace

        from catalog.seo import generate_meta_description

        product = SimpleNamespace(
            name="ACEITE DE JENGIBRE X1", price=Decimal("49900"), meta_description="", description_unique="",
            likely_free_shipping=False, description="ACEITE DE JENGIBRE – TERAPIA DE DRENAJE Activa tu bienestar natural.",
        )
        self.assertIn("envío a todo México. Activa tu bienestar", generate_meta_description(product))
