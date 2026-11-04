"""WhatsApp gratis: enlaces wa.me con el mensaje escrito (admin y confirmación)."""
from decimal import Decimal
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Order
from .whatsapp import admin_actions, customer_wa_number


class CustomerNumberTests(SimpleTestCase):
    def test_normalizes_mexican_mobiles(self):
        self.assertEqual(customer_wa_number("55 1234 5678"), "525512345678")
        self.assertEqual(customer_wa_number("+52 55-1234-5678"), "525512345678")
        self.assertEqual(customer_wa_number("+52 1 55 1234 5678"), "525512345678")
        self.assertEqual(customer_wa_number("0052 5512345678"), "525512345678")
        self.assertEqual(customer_wa_number("044 33 1234 5678"), "523312345678")
        self.assertEqual(customer_wa_number("123"), "")

    def test_never_uses_colombian_prefix(self):
        self.assertFalse(customer_wa_number("300 123 4567").startswith("57"))


class WhatsAppLinksTests(TestCase):
    def setUp(self):
        cache.clear()
        self.order = Order.objects.create(
            name="laura maría", surname="Mejía", phone="5512345678", address="Av. Juárez 1, col. Centro",
            city="Cuauhtémoc", state="CMX", total=Decimal("1299"),
            items=[{"name": "Organizador de baño", "quantity": 1, "price": "1299"}],
        )

    def _texts(self):
        return {a["key"]: (unquote(a["href"]), a["primary"]) for a in admin_actions(None, self.order)}

    def test_pending_order_suggests_confirming(self):
        actions = self._texts()
        text, primary = actions["confirm"]
        self.assertTrue(primary)
        self.assertIn("https://wa.me/525512345678?text=", text)
        self.assertIn("Hola Laura", text)
        self.assertIn("pedido #%d" % self.order.pk, text)
        self.assertIn("$1,299", text)
        self.assertNotIn("shipped", actions)

    def test_shipped_order_sends_full_guide_and_tracking(self):
        self.order.status = Order.STATUS_SENT
        self.order.shipping_guide = "2400123456789"
        self.order.carrier = "ENVIA"
        self.order.save()
        text, primary = self._texts()["shipped"]
        self.assertTrue(primary)
        self.assertIn("2400123456789", text)  # al cliente sí va completo
        self.assertIn("envia.com", text)

    def test_delivered_order_asks_for_review(self):
        self.order.status = Order.STATUS_DELIVERED
        self.order.save()
        text, primary = self._texts()["review"]
        self.assertTrue(primary)
        self.assertIn(f"/pedidos/opinar/{self.order.access_token}/", text)

    @override_settings(STORE_WHATSAPP="525512345678")
    def test_confirmation_page_has_customer_confirm_button(self):
        html = self.client.get(reverse("orders:confirmation", kwargs={"access_token": self.order.access_token})).content.decode()
        self.assertIn("Confirmar por WhatsApp", html)
        self.assertIn("confirmo%20mi%20pedido%20%23" + str(self.order.pk), html)

    def test_admin_shows_buttons(self):
        admin_user = get_user_model().objects.create_superuser("admin", "a@example.com", "x")
        self.client.force_login(admin_user)
        changelist = self.client.get(reverse("admin:orders_order_changelist")).content.decode()
        self.assertIn("Confirmar datos", changelist)
        change = self.client.get(reverse("admin:orders_order_change", args=[self.order.pk])).content.decode()
        self.assertIn("Abrir chat", change)
