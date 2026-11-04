import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from orders.models import Order

CANONICAL = "www.pegasusstoreco.com"
LEGACY = ["pegasusstoreco.com", "seashell-app-9wrdn.ondigitalocean.app"]
SECRET = "test-webhook-secret"


@override_settings(
    STORE_SITE_URL=f"https://{CANONICAL}",
    LEGACY_HOSTS=LEGACY,
    ALLOWED_HOSTS=[CANONICAL, *LEGACY, "testserver"],
    DROPI_WEBHOOK_SECRET=SECRET,
)
class CanonicalHostRedirectTests(TestCase):
    def test_legacy_hosts_redirect_301_keeping_path_and_query(self):
        for host in LEGACY:
            response = self.client.get("/producto/crema/?utm_source=ads&x=1", HTTP_HOST=host)
            self.assertEqual(response.status_code, 301, host)
            self.assertEqual(
                response["Location"],
                f"https://{CANONICAL}/producto/crema/?utm_source=ads&x=1",
            )

    @override_settings(PAGE_CACHE_SECONDS=300)
    def test_legacy_host_redirects_even_when_page_is_cached(self):
        # La caché de páginas no puede responder 200 en el host sin www.
        from django.core.cache import caches

        caches["pages"].clear()
        first = self.client.get("/", HTTP_HOST=CANONICAL)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.client.get("/", HTTP_HOST=CANONICAL)["X-Page-Cache"], "HIT")
        response = self.client.get("/", HTTP_HOST=LEGACY[0])
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], f"https://{CANONICAL}/")

    def test_canonical_host_is_not_redirected(self):
        response = self.client.get("/robots.txt", HTTP_HOST=CANONICAL)
        self.assertEqual(response.status_code, 200)

    def test_post_is_not_redirected(self):
        # Un 301 convierte el POST en GET y pierde el cuerpo del formulario.
        response = self.client.post("/pedidos/seguimiento/", {"guide": ""}, HTTP_HOST=LEGACY[0])
        self.assertNotEqual(response.status_code, 301)

    @override_settings(STORE_SITE_URL="")
    def test_disabled_without_store_site_url(self):
        response = self.client.get("/robots.txt", HTTP_HOST=LEGACY[0])
        self.assertEqual(response.status_code, 200)

    @override_settings(STORE_SITE_URL=f"https://{LEGACY[1]}")
    def test_never_redirects_a_host_to_itself(self):
        response = self.client.get("/robots.txt", HTTP_HOST=LEGACY[1])
        self.assertEqual(response.status_code, 200)

    @patch("orders.views.send_whatsapp_notification")
    @patch("orders.views.notify_status_change")
    def test_dropi_webhook_still_processed_on_every_host(self, _notify, _wa):
        # Sea cual sea el host configurado hoy en Dropi, el webhook debe
        # procesarse (no 301): un redirect haría que Dropi pierda el POST.
        order = Order.objects.create(
            name="A", surname="B", phone="3001234567", address="x",
            city="Medellín", state="Antioquia", total=Decimal("1"), items=[],
        )
        for host in [*LEGACY, CANONICAL]:
            Order.objects.filter(pk=order.pk).update(status=Order.STATUS_PENDING)
            body = json.dumps({"shop_order_id": order.pk, "status": "ENTREGADO"}).encode()
            sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
            response = self.client.post(
                "/pedidos/webhook/dropi/", body, content_type="application/json",
                HTTP_HOST=host, HTTP_X_DROPI_SIGNATURE=sig,
            )
            self.assertEqual(response.status_code, 200, host)
            self.assertTrue(response.json()["ok"], host)
            order.refresh_from_db()
            self.assertEqual(order.status, Order.STATUS_DELIVERED, host)

    def test_webhook_path_exempt_even_for_get(self):
        response = self.client.get("/pedidos/webhook/dropi/", HTTP_HOST=LEGACY[1])
        self.assertEqual(response.status_code, 405)  # require_POST, sin redirigir
