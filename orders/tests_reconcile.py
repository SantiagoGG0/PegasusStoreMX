"""Cruce de pedidos de la tienda con la lista de órdenes de Dropi."""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Order
from .reconcile import match_orders, reconcile


def _dropi(id_, status, *, shop_order_id=None, phone="3001234567", product="Gel Circuvena Flex", total=49900, days=0):
    return {
        "id": id_, "status": status, "shop_order_id": shop_order_id, "phone": phone, "total_order": total,
        "created_at": (timezone.now() + datetime.timedelta(days=days)).isoformat(),
        "orderdetails": [{"product": {"name": product}}], "shipping_guide": "G1" if status == "ENTREGADO" else "",
        "shipping_company": "ENVIA",
    }


class ReconcileTests(TestCase):
    def _order(self, **kw):
        data = dict(name="Ingrid", surname="P", phone="300 123 4567", address="x", city="Popayán", state="Cauca",
                    total=Decimal("49900"), items=[{"name": "GEL CIRCUVENA FLEX", "quantity": 1}])
        data.update(kw)
        return Order.objects.create(**data)

    def test_manual_reorder_with_same_product_wins_and_revives_cancelled(self):
        order = self._order(status=Order.STATUS_CANCELLED, cancel_reason="No se pudo procesar en Dropi: ciudad")
        dropi = [_dropi(1, "CANCELADO", shop_order_id=order.pk), _dropi(2, "ENTREGADO", days=1)]
        stats = reconcile(None, dropi_orders=dropi, local_orders=[order], notify_days=0)
        order.refresh_from_db()
        self.assertEqual((order.dropi_order_id, order.status), ("2", Order.STATUS_DELIVERED))
        self.assertEqual(stats["revived"], 1)

    def test_same_phone_different_product_is_not_matched(self):
        order = self._order(items=[{"name": "Cafetera Moka Italiana", "quantity": 1}], total=Decimal("36000"))
        dropi = [_dropi(3, "ENTREGADO", product="Bandeja organizadora silicona", total=165000, days=2)]
        self.assertEqual(match_orders([order], dropi), {})

    def test_customer_cancellation_is_not_revived(self):
        order = self._order(status=Order.STATUS_CANCELLED, cancelled_at=timezone.now())
        reconcile(None, dropi_orders=[_dropi(4, "ENTREGADO", shop_order_id=order.pk)], local_orders=[order], notify_days=0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)

    def test_manual_flag_cleared_when_order_exists_in_dropi(self):
        order = self._order(needs_manual_supplier=True)
        reconcile(None, dropi_orders=[_dropi(5, "GUIA_GENERADA", shop_order_id=order.pk)], local_orders=[order], notify_days=0)
        order.refresh_from_db()
        self.assertFalse(order.needs_manual_supplier)
        self.assertEqual(order.dropi_order_id, "5")
