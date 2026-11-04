"""
Cruza los pedidos de la tienda con la lista completa de órdenes de Dropi.

Por qué no basta con dropi_order_id: muchas órdenes fallaron al crearse o se
rehicieron a mano en el panel de Dropi (otra transportadora u otro
proveedor). La tienda guardaba el número de la primera orden, que ya no existe
o quedó cancelada, y el pedido se quedaba en "pendiente" o "cancelado" aunque
en Dropi estuviera entregado.

Cómo se empareja cada pedido local:
  1. Órdenes de Dropi con shop_order_id = pedido local (las que crea la tienda).
  2. Órdenes sin shop_order_id (hechas a mano) con el mismo celular, creadas
     hasta MANUAL_MATCH_DAYS después del pedido local.
De las candidatas se queda la "mejor": primero las que no están canceladas,
y entre ellas la más reciente.

Reglas al aplicar:
  - Se actualiza dropi_order_id a la orden elegida.
  - Un pedido cancelado por la tienda porque Dropi lo rechazó (no por el
    cliente: cancelled_at vacío) vuelve a la vida si en Dropi hay una orden
    activa o entregada para él.
  - needs_manual_supplier se apaga cuando ya existe una orden activa.
  - Los avisos al cliente (correo/WhatsApp) solo salen para pedidos recientes
    (notify_days); avisar en octubre que un pedido de julio fue entregado
    confunde más de lo que ayuda.
"""
from __future__ import annotations

import datetime
import logging
import re
import time

from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
PAGE_PAUSE_SECONDS = 11  # Dropi aguanta ~6 consultas por minuto
MANUAL_MATCH_DAYS = 10
_INACTIVE = {"CANCELADO", "ANULADO"}


def fetch_all_dropi_orders(client, *, pause: float = PAGE_PAUSE_SECONDS, max_pages: int = 60) -> list[dict]:
    orders: list[dict] = []
    for page in range(max_pages):
        data = client._get("orders/myorders", params={"result_number": PAGE_SIZE, "start": page * PAGE_SIZE}) or {}
        batch = data.get("objects") or []
        orders.extend(o for o in batch if isinstance(o, dict))
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(pause)
    return orders


def _phone_key(phone) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    return digits[-10:]


def _created(order: dict):
    value = order.get("created_at")
    parsed = parse_datetime(str(value)) if value else None
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime.timezone.utc)
    return parsed


_STOP = {"para", "con", "de", "del", "los", "las", "combo", "unidades", "set", "kit", "x2", "x3"}


def _words(text: str) -> set[str]:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return {w for w in re.findall(r"[a-z]{4,}", text) if w not in _STOP}


def _local_products(order) -> set[str]:
    words: set[str] = set()
    for item in order.items or []:
        if isinstance(item, dict):
            words |= _words(item.get("name"))
    return words


def _dropi_products(order: dict) -> set[str]:
    words: set[str] = set()
    for detail in order.get("orderdetails") or []:
        product = detail.get("product") if isinstance(detail, dict) else None
        if isinstance(product, dict):
            words |= _words(product.get("name"))
    return words


def _same_purchase(local, dropi: dict) -> bool:
    """Una orden hecha a mano corresponde al pedido si comparte algún producto
    o tiene el mismo total. Solo el teléfono no alcanza: las pruebas internas
    usan el mismo celular para compras distintas."""
    if _local_products(local) & _dropi_products(dropi):
        return True
    try:
        return abs(float(dropi.get("total_order") or 0) - float(local.total or 0)) < 1
    except (TypeError, ValueError):
        return False


def _rank(order: dict) -> tuple:
    status = str(order.get("status") or "").upper()
    created = _created(order) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    return (status not in _INACTIVE, created)


def match_orders(local_orders, dropi_orders: list[dict]) -> dict[int, dict]:
    """{pedido_local_pk: orden_de_dropi_elegida}."""
    by_shop_id: dict[int, list[dict]] = {}
    manual: list[dict] = []
    for d in dropi_orders:
        try:
            shop_id = int(d.get("shop_order_id") or 0)
        except (TypeError, ValueError):
            shop_id = 0
        if shop_id > 0:
            by_shop_id.setdefault(shop_id, []).append(d)
        else:
            manual.append(d)

    matches: dict[int, dict] = {}
    used_manual: set = set()
    for order in sorted(local_orders, key=lambda o: o.created_at):
        candidates = list(by_shop_id.get(order.pk, []))
        phone = _phone_key(order.phone)
        if phone:
            window_end = order.created_at + datetime.timedelta(days=MANUAL_MATCH_DAYS)
            for d in manual:
                created = _created(d)
                if (
                    d.get("id") not in used_manual
                    and _phone_key(d.get("phone")) == phone
                    and created is not None
                    and order.created_at - datetime.timedelta(hours=1) <= created <= window_end
                    and _same_purchase(order, d)
                ):
                    candidates.append(d)
        if candidates:
            best = max(candidates, key=_rank)
            matches[order.pk] = best
            if not best.get("shop_order_id"):
                used_manual.add(best.get("id"))
    return matches


def reconcile(client, *, dry_run: bool = False, notify_days: int = 3, local_orders=None, dropi_orders=None) -> dict:
    from .models import Order
    from .services import notify_status_change, send_whatsapp_notification, sync_order_from_dropi

    if dropi_orders is None:
        dropi_orders = fetch_all_dropi_orders(client)
    if local_orders is None:
        local_orders = list(Order.objects.all())
    matches = match_orders(local_orders, dropi_orders)
    notify_since = timezone.now() - datetime.timedelta(days=notify_days)
    stats = {"dropi_orders": len(dropi_orders), "matched": len(matches), "changed": 0, "revived": 0, "notified": 0, "rows": []}

    for order in local_orders:
        best = matches.get(order.pk)
        if not best:
            continue
        before = (order.status, order.dropi_order_id, order.needs_manual_supplier)
        best_status = str(best.get("status") or "").upper()
        if dry_run:
            stats["rows"].append((order.pk, before[0], best.get("id"), best_status))
            continue

        fields = []
        new_id = str(best.get("id") or "")
        if new_id and new_id != order.dropi_order_id:
            order.dropi_order_id = new_id
            fields.append("dropi_order_id")
        if best_status not in _INACTIVE:
            if order.status == Order.STATUS_CANCELLED and order.cancelled_at is None:
                # Cancelado por la tienda cuando Dropi rechazó la orden; luego
                # se rehízo a mano: se deja que el estado de Dropi mande.
                order.status = Order.STATUS_PENDING
                fields.append("status")
                stats["revived"] += 1
            if order.needs_manual_supplier:
                order.needs_manual_supplier = False
                fields.append("needs_manual_supplier")
        if fields:
            order.save(update_fields=fields)

        old_status = before[0]
        changed, _ = sync_order_from_dropi(order, {"objects": best})
        if changed or fields:
            stats["changed"] += 1
        stats["rows"].append((order.pk, old_status, best.get("id"), best_status, order.status))
        if order.status != old_status and order.created_at >= notify_since:
            for notify in (notify_status_change, send_whatsapp_notification):
                try:
                    notify(order, old_status)
                except Exception:
                    logger.exception("Aviso de estado falló para el pedido #%s", order.pk)
            stats["notified"] += 1
    return stats
