"""
Mensajes de WhatsApp sin API (gratis): enlaces wa.me con el texto ya escrito.

- Del equipo al cliente: botones en el admin del pedido. Abren WhatsApp
  (web o app) con el mensaje listo; la persona solo pulsa enviar.
- Del cliente a la tienda: "Confirmar mi pedido por WhatsApp" en la página de
  confirmación. Además de confirmar el pedido (menos devoluciones), abre la
  ventana de servicio de 24 h si algún día se usa la API oficial de Meta.

Los textos van sin emojis raros ni enlaces acortados: WhatsApp los muestra
tal cual y el cliente confía más en un enlace del dominio de la tienda.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from django.urls import reverse

from catalog.store_config import store_config
from config.site import absolute_url


def customer_wa_number(phone: str) -> str:
    """Celular del cliente en formato wa.me (solo dígitos, con 52).
    "55 1234 5678" → "525512345678". Vacío si no parece un número válido."""
    from orders.forms import normalize_phone

    digits = normalize_phone(phone)
    if len(digits) == 10:
        digits = "52" + digits
    return digits if 12 <= len(digits) <= 15 else ""


def wa_link(number: str, text: str) -> str:
    return f"https://wa.me/{number}?text={quote(text)}" if number else ""


def _first_name(order) -> str:
    return (order.name or "").strip().split(" ")[0].title()


def _money(value) -> str:
    return "$" + f"{int(round(float(value or 0))):,}"


def _items_line(order) -> str:
    names = [
        f"{item.get('name', '')} x{item.get('quantity', 1)}"
        for item in (order.items or [])
        if isinstance(item, dict) and item.get("name")
    ]
    return ", ".join(names[:4]) + ("…" if len(names) > 4 else "")


def order_detail_url(request, order) -> str:
    return absolute_url(request, reverse("orders:detail", kwargs={"access_token": order.access_token}))


def order_review_url(request, order) -> str:
    return absolute_url(request, reverse("orders:review", kwargs={"access_token": order.access_token}))


def tracking_url(order) -> str:
    from .services import build_tracking_url

    if (order.tracking_url or "").startswith("http"):
        return order.tracking_url
    return build_tracking_url(order.carrier or "", order.shipping_guide or "")


# ── Del equipo al cliente (admin) ─────────────────────────────────────────────

def msg_confirm_order(request, order) -> str:
    return (
        f"Hola {_first_name(order)}, te escribimos de Pegasus Store por tu pedido #{order.pk}: "
        f"{_items_line(order)}. Total {_money(order.total)}, pagas al recibir.\n"
        f"Dirección: {order.address}, {order.city}.\n"
        "¿Nos confirmas que los datos están bien y que vas a poder recibirlo? Gracias."
    )


def msg_shipped(request, order) -> str:
    carrier = f" con {order.carrier}" if order.carrier else ""
    url = tracking_url(order)
    track = f"\nRastréalo aquí: {url}" if url else ""
    return (
        f"Hola {_first_name(order)}, tu pedido #{order.pk} de Pegasus Store ya va en camino{carrier}.\n"
        f"Número de guía: {order.shipping_guide}{track}\n"
        f"Ten a la mano {_money(order.total)} para pagarle al repartidor cuando lo revises.\n"
        f"Detalle del pedido: {order_detail_url(request, order)}"
    )


def msg_delivered_review(request, order) -> str:
    return (
        f"Hola {_first_name(order)}, vimos que tu pedido #{order.pk} ya fue entregado. ¡Gracias por comprar en Pegasus Store!\n"
        "¿Nos ayudas con tu opinión? Toma 1 minuto y le sirve mucho a otros clientes:\n"
        f"{order_review_url(request, order)}"
    )


def admin_actions(request, order) -> list[dict]:
    """Botones para el admin: [{label, href, primary}], el que toca según el
    estado va primero y resaltado."""
    from .models import Order

    number = customer_wa_number(order.phone)
    if not number:
        return []
    actions = [
        {"key": "confirm", "label": "Confirmar datos", "href": wa_link(number, msg_confirm_order(request, order))},
    ]
    if order.shipping_guide:
        actions.append({"key": "shipped", "label": "Enviar guía", "href": wa_link(number, msg_shipped(request, order))})
    if order.status == Order.STATUS_DELIVERED:
        actions.append({"key": "review", "label": "Pedir reseña", "href": wa_link(number, msg_delivered_review(request, order))})
    actions.append({"key": "chat", "label": "Abrir chat", "href": f"https://wa.me/{number}"})

    if order.status == Order.STATUS_DELIVERED:
        primary = "review"
    elif order.shipping_guide and order.status != Order.STATUS_CANCELLED:
        primary = "shipped"
    elif order.status == Order.STATUS_PENDING:
        primary = "confirm"
    else:
        primary = ""
    for action in actions:
        action["primary"] = action["key"] == primary
    return actions


# ── Del cliente a la tienda (página de confirmación) ──────────────────────────

def customer_confirm_link(order) -> str:
    text = (
        f"Hola, confirmo mi pedido #{order.pk} a nombre de {order.name} {order.surname}. "
        f"Entrega en {order.city}. Total {_money(order.total)}, pago al recibir. "
        "¿Me avisan por aquí cuando salga?"
    )
    return wa_link(store_config()["whatsapp"], text)
