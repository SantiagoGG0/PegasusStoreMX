"""Rediseño de conversión (oct 2026): nombre visible, descripción sin
garantía del proveedor, tiempos de entrega coherentes, reseñas desde el
pedido, "lo más pedido" y prueba social real."""
import datetime
import json
import re
from decimal import Decimal

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product, ProductReview
from catalog.services.delivery import add_business_days, dispatch_date, dispatch_label
from catalog.services.description_sanitizer import clean_description_for_display, extract_highlights
from catalog.services.naming import build_vocabulary, clean_display_name
from orders.models import Order


class DisplayNameTests(SimpleTestCase):
    def test_removes_internal_tags_emojis_and_cut_word(self):
        vocab = build_vocabulary(["Organizador acrílico para baño"] * 3)
        self.assertEqual(clean_display_name("Organizador Maquillaje Acrílico Giratori", vocab), "Organizador Maquillaje Acrílico")
        self.assertEqual(clean_display_name("MINI PROYECTOR LED YG300 DROPI CUP"), "Mini Proyector LED YG300")
        self.assertEqual(clean_display_name("Combo Organiza Y Renueva Tu Hogar 🏡✨"), "Combo Organiza y Renueva Tu Hogar")

    def test_keeps_complete_names_and_acronyms(self):
        vocab = build_vocabulary(["Ventilador multifuncional"] * 3)
        self.assertEqual(clean_display_name("Ventilador De Panel Solar Multifuncional", vocab), "Ventilador de Panel Solar Multifuncional")
        self.assertEqual(clean_display_name("Consola M25 Video Juegos Portátil PSP"), "Consola M25 Video Juegos Portátil PSP")
        self.assertEqual(clean_display_name("Aro Luz 45cm Led Rgb Con Trípode"), "Aro Luz 45cm LED RGB con Trípode")

    def test_drops_trailing_connector_and_single_letter(self):
        self.assertEqual(clean_display_name("SET DESTORNILLADOR CON PUNTAS CON"), "Set Destornillador con Puntas")
        self.assertEqual(clean_display_name("Protector Desechable Para Inodoro D"), "Protector Desechable para Inodoro")


class DescriptionForDisplayTests(SimpleTestCase):
    RAW = (
        "Consola Retro Portátil: Un dispositivo de juegos portátil. Funciones: Pantalla IPS: Imágenes nítidas y claras. "
        "Batería Duradera: Con 4000 mAh garantiza hasta 5 horas de juego. Uso Versátil: Ideal para viajes. "
        "Material: ABS Garantía: Cuenta con 10 días de garantía por defectos de fábrica únicamente, daños ocasionados "
        "por terceros no cubre garantía. Nota: Para devoluciones tener en cuenta el embalaje."
    )

    def test_cuts_supplier_warranty_but_keeps_features(self):
        text = " ".join(clean_description_for_display(self.RAW))
        self.assertNotIn("10 días", text)
        self.assertNotIn("terceros", text)
        self.assertNotIn("devoluciones", text)
        self.assertIn("garantiza hasta 5 horas", text)  # "garantiza" no es la garantía del proveedor

    def test_drops_contacts_and_dropi(self):
        paragraphs = clean_description_for_display("<p>Lindo y útil.</p><p>Pedidos al 3001234567 o en Dropi.</p>")
        self.assertEqual(paragraphs, ["Lindo y útil."])

    def test_highlights_from_feature_labels(self):
        highlights = extract_highlights(clean_description_for_display(self.RAW), "Consola M25")
        # Rótulo con valor corto → "Rótulo: valor"; con explicación larga → solo el rótulo.
        self.assertEqual(highlights[:3], ["Pantalla IPS: Imágenes nítidas y claras", "Batería Duradera", "Uso Versátil: Ideal para viajes"])

    def test_no_highlights_when_too_few(self):
        self.assertEqual(extract_highlights(["Un producto muy útil para la casa."]), [])


class DeliveryTests(SimpleTestCase):
    def _at(self, y, m, d, hour):
        from django.utils import timezone

        return timezone.make_aware(datetime.datetime(y, m, d, hour, 0))

    def test_dispatch_same_day_before_cutoff(self):
        monday_morning = self._at(2026, 10, 12, 9)
        self.assertEqual(dispatch_date(monday_morning, cutoff=14), datetime.date(2026, 10, 12))
        self.assertEqual(dispatch_label(monday_morning, cutoff=14), "Sale hoy")

    def test_dispatch_after_cutoff_and_weekend(self):
        self.assertEqual(dispatch_label(self._at(2026, 10, 12, 16), cutoff=14), "Sale mañana")
        self.assertEqual(dispatch_label(self._at(2026, 10, 17, 10), cutoff=14), "Sale el lunes")  # sábado

    def test_business_days_skip_weekend(self):
        self.assertEqual(add_business_days(datetime.date(2026, 10, 16), 1), datetime.date(2026, 10, 19))


class StorefrontTrustTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(dropi_id="store:hogar", name="Hogar")
        self.product = Product.objects.create(
            dropi_id=1, name="ORGANIZADOR DE BAÑO DROPI CUP", slug="organizador", category=self.cat,
            price=Decimal("59900"), cost=Decimal("20000"), stock=40, is_active=True,
            images=["https://x/1.jpg", "https://x/2.jpg"],
            description="<p>Estante: Tres niveles. Material: Plástico. Fácil de armar: Sin tornillos.</p>"
                        "<p>Garantía: 10 días por defectos de fábrica.</p>",
        )
        self.order = Order.objects.create(
            name="laura maría", surname="mejía", phone="5512345678", address="x", city="guadalajara",
            state="JAL", total=Decimal("599"), status=Order.STATUS_DELIVERED,
            items=[{"local_id": self.product.pk, "name": self.product.name, "quantity": 1}],
        )

    def test_pdp_shows_clean_name_trust_strip_and_no_supplier_warranty(self):
        html = self.client.get(self.product.get_absolute_url()).content.decode()
        self.assertIn("Organizador de Baño", html)
        self.assertNotIn("DROPI CUP", html)
        self.assertIn("pdp-trust", html)
        self.assertIn("Pregúntanos por WhatsApp", html)
        self.assertNotIn("10 días por defectos", html)
        self.assertIn("ref.%20PGS-", html)  # mensaje de WhatsApp con la referencia

    def test_order_review_flow_publishes_verified_review(self):
        url = reverse("orders:review", kwargs={"access_token": self.order.access_token})
        page = self.client.get(url)
        self.assertContains(page, "Laura M., Guadalajara")
        response = self.client.post(url, {f"score_{self.product.pk}": "5", f"comment_{self.product.pk}": "Llegó perfecto"})
        self.assertEqual(response.status_code, 302)
        review = ProductReview.objects.get()
        self.assertEqual((review.score, review.author_name, review.order_id, review.user_id), (5, "Laura M.", self.order.pk, None))
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 1)

        home = self.client.get("/").content.decode()
        self.assertIn("Llegó perfecto", home)
        self.assertIn("Compra verificada", home)

    def test_review_requires_delivered_order(self):
        self.order.status = Order.STATUS_SENT
        self.order.save()
        url = reverse("orders:review", kwargs={"access_token": self.order.access_token})
        self.client.post(url, {f"score_{self.product.pk}": "5"})
        self.assertFalse(ProductReview.objects.exists())

    def test_home_has_bestsellers_faq_schema_and_no_marquee(self):
        html = self.client.get("/").content.decode()
        self.assertIn('id="mas-pedidos"', html)
        self.assertIn("Organizador de Baño", html)
        self.assertNotIn("marquee__track", html)
        self.assertNotIn("24/7", html)
        ld = json.loads(re.search(r'(?s)<script type="application/ld\+json">(.*?)</script>', html).group(1))
        types = {node["@type"] for node in ld["@graph"]}
        self.assertTrue({"WebSite", "OnlineStore", "FAQPage"} <= types)

    def test_about_page_and_footer_identity(self):
        html = self.client.get(reverse("pages:about")).content.decode()
        self.assertIn("Quiénes somos", html)
        self.assertIn("gob.mx/profeco", html)

    def test_cities_json(self):
        data = self.client.get(reverse("cart:cities_json")).json()
        self.assertIn(["Guadalajara", "Jalisco"], data["cities"])

    def test_zip_lookup_fills_state_and_city(self):
        data = self.client.get(reverse("cart:zip_lookup", kwargs={"zip_code": "44100"})).json()
        self.assertEqual(data["matches"], [{"state": "JAL", "state_label": "Jalisco", "city": "Guadalajara"}])

    def test_zip_lookup_unknown_zip_returns_no_matches(self):
        data = self.client.get(reverse("cart:zip_lookup", kwargs={"zip_code": "99999"})).json()
        self.assertEqual(data["matches"], [])

    def test_checkout_template_has_zip_field_before_state(self):
        from django.template.loader import get_template

        source = get_template("orders/checkout.html").template.source
        self.assertLess(source.index('data-field="zip_code"'), source.index('data-field="state"'))
        self.assertIn("cart:zip_lookup", source)


class StoreSettingsTests(TestCase):
    """Los datos de la tienda se editan en el admin; vacío = valor de settings."""

    def setUp(self):
        cache.clear()

    @override_settings(STORE_NIT="", STORE_SUPPORT_HOURS="")
    def test_admin_values_reach_footer_trust_faq_and_json_ld(self):
        from catalog.models import StoreSettings

        html = self.client.get(reverse("pages:trust")).content.decode()
        self.assertNotIn("RFC ", html)

        StoreSettings.objects.create(nit="PST250101AB1", support_hours="Lunes a sábado, 8 a. m. a 6 p. m.", dispatch_cutoff_hour=11)
        html = self.client.get(reverse("pages:trust")).content.decode()
        self.assertIn("RFC PST250101AB1", html)  # footer
        self.assertIn("Lunes a sábado, 8 a. m. a 6 p. m.", html)
        self.assertIn('"taxID": "PST250101AB1"', html)  # JSON-LD
        self.assertIn("RFC PST250101AB1, con sede", html)  # FAQ

        from catalog.store_config import store_config

        self.assertEqual(store_config()["dispatch_cutoff_hour"], 11)

    @override_settings(STORE_EMAIL="env@example.com")
    def test_blank_field_falls_back_to_settings(self):
        from catalog.models import StoreSettings
        from catalog.store_config import store_config

        StoreSettings.objects.create(email="")
        self.assertEqual(store_config()["email"], "env@example.com")

    def test_admin_is_a_single_page(self):
        from django.contrib.auth import get_user_model

        admin_user = get_user_model().objects.create_superuser("admin", "a@example.com", "x")
        self.client.force_login(admin_user)
        changelist = reverse("admin:catalog_storesettings_changelist")
        response = self.client.get(changelist)
        self.assertRedirects(response, reverse("admin:catalog_storesettings_change", args=[1]))
        page = self.client.get(reverse("admin:catalog_storesettings_change", args=[1]))
        self.assertContains(page, "Valores en uso ahora")


class MerchantFeedPersistenceTests(TestCase):
    """El feed sobrevive a un despliegue (copia en la base de datos), no
    incluye casi duplicados y declara la categoría de Google."""

    def setUp(self):
        cat = Category.objects.create(dropi_id="store:cocina", name="Cocina")
        base = dict(category=cat, cost=Decimal("10000"), stock=5, is_active=True, price=Decimal("60000"))
        self.main = Product.objects.create(dropi_id=1, name="Organizador", slug="org", images=[{"url": "https://cdn/a.jpg"}], **base)
        Product.objects.create(dropi_id=2, name="Organizador", slug="org-2", images=[{"url": "https://cdn/b.jpg"}],
                               canonical_product=self.main, **base)

    def test_snapshot_restores_feed_after_restart(self):
        import tempfile
        import xml.etree.ElementTree as ET
        from pathlib import Path
        from unittest import mock

        from django.test import RequestFactory

        from catalog import feeds
        from catalog.models import FeedSnapshot

        path = Path(tempfile.mkdtemp()) / "feed.xml"
        self.assertEqual(feeds.write_feed(RequestFactory().get("/"), path), 1)  # sin el duplicado
        self.assertEqual(FeedSnapshot.objects.get().item_count, 1)

        path.unlink()  # el contenedor se reinicia y pierde /tmp
        with mock.patch.object(feeds, "FEED_FILE", path), mock.patch.object(feeds, "_regenerate_in_background") as regen:
            response = self.client.get("/feeds/google-merchant.xml")
        self.assertEqual(response.status_code, 200)
        regen.assert_not_called()  # la copia es reciente: no hace falta regenerar
        root = ET.fromstring(b"".join(response.streaming_content))
        ns = {"g": "http://base.google.com/ns/1.0"}
        item = root.find("channel/item")
        self.assertEqual(item.find("g:google_product_category", ns).text, "Home & Garden > Kitchen & Dining")
