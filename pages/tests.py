from decimal import Decimal
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from orders.models import Order


class TrustPageTests(TestCase):
    """/confianza/ daba 500 en producción. Debe cargar siempre, sin contenido
    inventado (chats escritos a mano, recuadros de fotos vacíos)."""

    def _order(self, **kwargs):
        data = dict(
            name="A", surname="B", phone="3001234567", address="x",
            city="Medellín", state="Antioquia", total=Decimal("1"), items=[],
        )
        data.update(kwargs)
        return Order.objects.create(**data)

    def test_loads_without_orders_and_hides_empty_sections(self):
        response = self.client.get(reverse("pages:trust"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn("Guías despachadas", html)
        self.assertNotIn("FOTO DE ENTREGA", html)
        self.assertNotIn("María G.", html)

    def test_tolerates_incomplete_order_data(self):
        self._order(shipping_guide="   ", status=Order.STATUS_SENT)
        self._order(shipping_guide="GU123", city="", items={"raro": True}, status=Order.STATUS_DELIVERED)
        self._order(shipping_guide="GU999", status="ESTADO_DESCONOCIDO")
        response = self.client.get(reverse("pages:trust"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("GU•••", html)  # número parcial
        self.assertIn("1 paquete", html)
        self.assertNotIn("GU9", html)  # solo guías despachadas o entregadas
        self.assertNotIn("Bogotá →", html)

    def test_no_unverifiable_claims(self):
        html = self.client.get(reverse("pages:trust")).content.decode()
        self.assertNotIn("5 años", html)
        self.assertNotIn("Cinco años", html)
        self.assertNotIn("24/7", html)
        self.assertIn("¿Pegasus Store es confiable?", html)
        self.assertIn("FAQPage", html)

    def test_guide_number_is_partial_and_not_linked(self):
        # El número completo deja ver en la transportadora el nombre y la
        # dirección del cliente: en público va parcial y sin enlace.
        self._order(shipping_guide="2400123456789", carrier="SERVIENTREGA", city="medellin", status=Order.STATUS_DELIVERED)
        html = self.client.get(reverse("pages:trust")).content.decode()
        self.assertIn("2400••••••789", html)
        self.assertNotIn("2400123456789", html)
        self.assertNotIn("servientrega.com.co", html)
        self.assertIn("Medellín", html)

    def test_database_error_does_not_break_the_page(self):
        with patch("orders.models.Order.objects.filter", side_effect=DatabaseError("columna inexistente")):
            with self.assertLogs("catalog.services.trust", level="ERROR"):
                response = self.client.get(reverse("pages:trust"))
        self.assertEqual(response.status_code, 200)
