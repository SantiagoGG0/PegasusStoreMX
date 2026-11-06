"""Order access and notification helpers."""

from __future__ import annotations

import logging
import re
import unicodedata

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

from .models import Order

logger = logging.getLogger(__name__)

_MAGIC_LINK_SALT = "pegasus-order-access"
_MAGIC_LINK_MAX_AGE = 60 * 60  # 1 hour


def sign_order_access_email(email: str) -> str:
    signer = signing.TimestampSigner(salt=_MAGIC_LINK_SALT)
    return signer.sign(email.strip().lower())


def unsign_order_access_email(token: str) -> str | None:
    signer = signing.TimestampSigner(salt=_MAGIC_LINK_SALT)
    try:
        return signer.unsign(token, max_age=_MAGIC_LINK_MAX_AGE)
    except signing.BadSignature:
        return None


def send_order_access_email(request, email: str) -> bool:
    """Send a magic link to view orders for the given email."""
    token = sign_order_access_email(email)
    path = reverse("orders:access_verify", kwargs={"token": token})
    link = request.build_absolute_uri(path)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@pegasusstoremx.com")
    subject = "Accede a tus pedidos — Pegasus Store"
    body = (
        f"Hola,\n\n"
        f"Solicitaste ver tus pedidos en Pegasus Store. Usa este enlace (válido 1 hora):\n\n"
        f"{link}\n\n"
        f"Si no solicitaste esto, ignora este mensaje.\n\n"
        f"— Equipo Pegasus Store"
    )
    try:
        send_mail(subject, body, from_email, [email], fail_silently=False)
        return True
    except Exception as exc:
        logger.error("Failed to send order access email to %s: %s", email, exc)
        return False


def orders_for_email(email: str):
    return Order.objects.filter(email__iexact=email.strip()).order_by("-created_at")


def extract_shipping_from_dropi(objects: dict) -> tuple:
    """Return (shipping_cost, products_subtotal_hint) from Dropi response objects."""
    from decimal import Decimal

    if not isinstance(objects, dict):
        return Decimal("0"), None

    for key in ("shipping_cost", "shipping", "cost_shipping", "total_shipping"):
        val = objects.get(key)
        if val is not None:
            try:
                shipping = Decimal(str(val))
                total = objects.get("total_order") or objects.get("total")
                if total is not None:
                    return shipping, Decimal(str(total)) - shipping
                return shipping, None
            except Exception:
                pass
    return Decimal("0"), None


def extract_tracking_from_webhook(data: dict) -> tuple[str, str]:
    """Return (carrier, tracking_url) from webhook payload."""
    carrier = (
        data.get("carrier")
        or data.get("transportadora")
        or data.get("shipping_company")
        or ""
    )
    tracking_url = (
        data.get("tracking_url")
        or data.get("guide_url")
        or data.get("url_tracking")
        or data.get("tracking_link")
        or ""
    )
    if not tracking_url and data.get("guide_number"):
        tracking_url = str(data.get("guide_number"))
    return str(carrier)[:120], str(tracking_url)[:500]


# ── Carrier tracking URL builder ─────────────────────────────────────────────

# Maps normalised carrier name substrings → tracking URL template (use {guide}).
# Keys are checked as substrings of the uppercased carrier name, in order.
# Solo respaldo: primero se usa el enlace de seguimiento que manda Dropi en el
# webhook. Se quitaron las paqueterías de Colombia (Servientrega, TCC,
# Interrapidísimo...). Quality-post, Tiui y Coordi (las que cotiza Dropi
# México) se agregan con el formato real de sus guías en los primeros pedidos.
_CARRIER_TRACKING = [
    ("VELOCES",         "https://tracking.veloces.app/"),
    ("ENVIA",           "https://app.envia.com/tracking/{guide}"),
    ("FEDEX",           "https://www.fedex.com/fedextrack/?trknbr={guide}"),
]


def build_tracking_url(carrier: str, guide: str) -> str:
    """
    Return a tracking URL for the given carrier and guide number.
    Returns empty string if the carrier is unknown or guide is empty.
    """
    if not guide or not carrier:
        return ""
    key = carrier.upper().strip()
    for fragment, template in _CARRIER_TRACKING:
        if fragment in key:
            return template.format(guide=guide)
    return ""


# ── Status synchronisation ────────────────────────────────────────────────────

# Maps raw Dropi status strings → local Order status constants.
# Keys are normalised to uppercase with stripped whitespace at lookup time.
_DROPI_TO_LOCAL = {
    "PENDIENTE": "PENDIENTE CONFIRMACION",
    "CREADO": "PENDIENTE CONFIRMACION",
    "NUEVO": "PENDIENTE CONFIRMACION",
    "POR CONFIRMAR": "PENDIENTE CONFIRMACION",
    "PENDIENTE DE CONFIRMACION": "PENDIENTE CONFIRMACION",
    "PENDIENTE CONFIRMACION": "PENDIENTE CONFIRMACION",
    "PENDIENTE DE CONFIRMACION DE DATOS": "PENDIENTE CONFIRMACION",
    "PENDIENTE DE PAGO": "PENDIENTE CONFIRMACION",
    "PAGO PENDIENTE": "PENDIENTE CONFIRMACION",
    "CONFIRMADO": "CONFIRMADO",
    "APROBADO": "CONFIRMADO",
    "PAGADO": "CONFIRMADO",
    "EN ALISTAMIENTO": "CONFIRMADO",
    "ALISTANDO": "CONFIRMADO",
    "ALISTADO": "CONFIRMADO",
    "PROCESANDO": "CONFIRMADO",
    "PROCESADO": "CONFIRMADO",
    "EMPAQUE": "CONFIRMADO",
    "EMPAQUETANDO": "CONFIRMADO",
    "RECIBIDO PAU": "CONFIRMADO",
    "PAU": "CONFIRMADO",
    "GUIA_GENERADA": "CONFIRMADO",
    "GUIA GENERADA": "CONFIRMADO",
    "GUIA CREADA": "CONFIRMADO",
    "ETIQUETA GENERADA": "CONFIRMADO",
    "EN BODEGA DROPI": "CONFIRMADO",
    "EN BODEGA": "CONFIRMADO",
    "LISTO PARA ENVIAR": "CONFIRMADO",
    "LISTO PARA DESPACHO": "CONFIRMADO",
    "PREPARANDO": "CONFIRMADO",
    "ENVIADO": "ENVIADO",
    "DESPACHADO": "ENVIADO",
    "DESPACHADA": "ENVIADO",
    "SALIO A DISTRIBUCION": "ENVIADO",
    "SALIO A RUTA": "ENVIADO",
    "ENTREGADO A TRANSPORTADORA": "ENVIADO",
    "RECIBIDO POR TRANSPORTADORA": "ENVIADO",
    "RECIBIDO EN TRANSPORTADORA": "ENVIADO",
    "RECOGIDO POR TRANSPORTADORA": "ENVIADO",
    "EN BODEGA ORIGEN": "ENVIADO",
    "EN BODEGA DESTINO": "ENVIADO",
    "EN CLASIFICACION": "ENVIADO",
    "EN CLASIFICACIÓN": "ENVIADO",
    "EN CLASIFICACION ORIGEN": "ENVIADO",
    "EN CLASIFICACION DESTINO": "ENVIADO",
    "EN CENTRO DE DISTRIBUCION": "ENVIADO",
    "EN HUB": "ENVIADO",
    "EN REPARTO": "ENVIADO",
    "SALIO A REPARTO": "ENVIADO",
    "EN DISTRIBUCION": "ENVIADO",
    "EN RUTA": "ENVIADO",
    "EN CAMINO": "ENVIADO",
    "EN TRANSITO": "ENVIADO",
    "EN TRÁNSITO": "ENVIADO",
    "INTENTO DE ENTREGA": "ENVIADO",
    "EN NOVEDAD": "ENVIADO",
    "NOVEDAD": "ENVIADO",
    "ENTREGADO": "ENTREGADO",
    "ENTREGA EXITOSA": "ENTREGADO",
    "FINALIZADO": "ENTREGADO",
    "FINALIZADA": "ENTREGADO",
    "CANCELADO": "CANCELADO",
    "ANULADO": "CANCELADO",
    "RECHAZADO": "CANCELADO",
    "RECHAZADA": "CANCELADO",
    "DEVOLUCION": "CANCELADO",
    "DEVOLUCION EN PROCESO": "CANCELADO",
    "DEVUELTO AL REMITENTE": "CANCELADO",
    "NO ENTREGADO": "CANCELADO",
    "DEVUELTO": "CANCELADO",
    "NO RECLAMADO": "CANCELADO",
}


def _normalize_dropi_status(raw_status: str) -> str:
    """Normalize Dropi status for robust matching (accents, spaces, punctuation)."""
    s = (raw_status or "").strip().upper()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _map_dropi_status(raw_status: str) -> str:
    """
    Map Dropi raw status to local Order status.
    Tries exact dictionary match first, then keyword heuristics.
    """
    normalized = _normalize_dropi_status(raw_status)
    if not normalized:
        return ""

    exact = _DROPI_TO_LOCAL.get(normalized)
    if exact:
        return exact

    # Heuristics for unseen variants from carriers/Dropi.
    if "ENTREG" in normalized or "FINALIZ" in normalized:
        return Order.STATUS_DELIVERED
    if any(k in normalized for k in ("CANCEL", "ANUL", "RECHAZ", "DEVUEL", "NO RECLAM")):
        return Order.STATUS_CANCELLED
    if any(
        k in normalized
        for k in (
            "TRANSPORT",
            "TRANSITO",
            "RUTA",
            "REPARTO",
            "DESPACH",
            "BODEGA ORIGEN",
            "BODEGA DESTINO",
            "CLASIFIC",
            "DISTRIBUC",
            "HUB",
            "NOV",
            "GUIA",
        )
    ):
        return Order.STATUS_SENT
    if any(k in normalized for k in ("CONFIRM", "ALIST", "BODEGA", "PAGAD", "APROBAD", "PAU")):
        return Order.STATUS_CONFIRMED
    if any(k in normalized for k in ("PENDIENT", "CREAD", "NUEV", "PAGO")):
        return Order.STATUS_PENDING
    return ""

_STATUS_LABELS = {
    "PENDIENTE CONFIRMACION": "Pendiente de confirmación",
    "CONFIRMADO": "Confirmado",
    "ENVIADO": "En camino",
    "ENTREGADO": "Entregado",
    "CANCELADO": "Cancelado",
}


def _extract_objects(data: dict) -> dict:
    """Return the inner 'objects' dict from a Dropi API response."""
    objects = data.get("objects")
    if isinstance(objects, list) and objects:
        return objects[0] if isinstance(objects[0], dict) else {}
    if isinstance(objects, dict):
        return objects
    return data  # fallback: treat entire response as data


def sync_order_from_dropi(order, dropi_data: dict) -> tuple[bool, str]:
    """
    Update *order* fields from a Dropi API response dict.

    Returns (changed: bool, old_local_status: str).
    Saves the order if any field changed.
    """
    from django.utils import timezone

    obj = _extract_objects(dropi_data)
    old_status = order.status

    # ── Map Dropi status → local status ──────────────────────────────────
    raw_dropi_status = str(
        obj.get("status") or obj.get("estado") or obj.get("order_status") or ""
    ).strip()
    local_status = _map_dropi_status(raw_dropi_status)

    # ── Extract guide / carrier ───────────────────────────────────────────
    # Dropi uses "shipping_guide" for the guide number (e.g. V4002607902)
    guide = str(
        obj.get("shipping_guide")
        or obj.get("guide_number")
        or obj.get("guide")
        or obj.get("tracking_number")
        or obj.get("numeral_guide")
        or obj.get("guia")
        or obj.get("numero_guia")
        or obj.get("tracking")
        or ""
    ).strip()
    carrier = str(
        obj.get("shipping_company")
        or obj.get("carrier")
        or obj.get("transportadora")
        or ""
    ).strip()[:120]
    tracking_url = str(
        obj.get("tracking_url") or obj.get("guide_url") or obj.get("url_tracking") or ""
    ).strip()[:500]

    # If Dropi didn't provide a URL, build one from carrier + guide
    if not tracking_url and guide and carrier:
        tracking_url = build_tracking_url(carrier, guide)

    changed = False
    update_fields = ["last_dropi_sync"]

    if raw_dropi_status and raw_dropi_status != order.dropi_status:
        order.dropi_status = raw_dropi_status
        update_fields.append("dropi_status")
        changed = True

    if local_status and local_status != order.status:
        # Never revert a cancelled or delivered order via sync
        if order.status not in ("CANCELADO", "ENTREGADO"):
            order.status = local_status
            update_fields.append("status")
            changed = True

    # ── Smart inference from guide / carrier ───────────────────────────
    # If Dropi hasn't updated its status yet but a guide exists, we can
    # infer the real state: guide + carrier = package handed to carrier = ENVIADO.
    # guide only (no carrier) = at least CONFIRMADO.
    if order.status not in ("CANCELADO", "ENTREGADO"):
        effective_guide = guide or order.shipping_guide
        effective_carrier = carrier or order.carrier
        if effective_guide and effective_carrier and order.status == Order.STATUS_PENDING:
            order.status = Order.STATUS_SENT
            if "status" not in update_fields:
                update_fields.append("status")
            changed = True
        elif effective_guide and order.status == Order.STATUS_PENDING:
            order.status = Order.STATUS_CONFIRMED
            if "status" not in update_fields:
                update_fields.append("status")
            changed = True

    if guide and guide != order.shipping_guide:
        order.shipping_guide = guide
        update_fields.append("shipping_guide")
        changed = True

    if carrier and carrier != order.carrier:
        order.carrier = carrier
        update_fields.append("carrier")
        changed = True

    if tracking_url and tracking_url != order.tracking_url:
        order.tracking_url = tracking_url
        update_fields.append("tracking_url")
        changed = True

    order.last_dropi_sync = timezone.now()
    order.save(update_fields=update_fields)
    return changed, old_status


def order_review_url(order) -> str:
    """URL absoluta para opinar sobre el pedido (solo tiene sentido entregado)."""
    from django.conf import settings
    from django.urls import reverse

    site = getattr(settings, "STORE_SITE_URL", "").rstrip("/")
    path = reverse("orders:review", kwargs={"access_token": order.access_token})
    return (site + path) if site else path


def notify_status_change(order, old_status: str) -> bool:
    """
    Send HTML email to customer when order status changes.
    Returns True if email sent successfully.
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from datetime import datetime

    # Status display mapping
    status_config = {
        "CONFIRMADO": {
            "label": "Confirmado",
            "emoji": "✅",
            "message": "Tu pedido fue confirmado y está siendo preparado por nuestro equipo.",
        },
        "ENVIADO": {
            "label": "En camino",
            "emoji": "🚚",
            "message": "¡Tu pedido ya está en camino! Pronto lo recibirás en tu dirección.",
        },
        "ENTREGADO": {
            "label": "Entregado",
            "emoji": "🎉",
            "message": "¡Tu pedido fue entregado con éxito! Esperamos que lo disfrutes.",
        },
        "CANCELADO": {
            "label": "Cancelado",
            "emoji": "❌",
            "message": "Tu pedido fue cancelado.",
        },
    }
    
    config = status_config.get(order.status)
    if not config:
        return False  # No notification for this status
    
    status_label = config["label"]
    subject = f"Tu pedido #{order.pk} — {status_label} — Pegasus Store"
    
    site_url = getattr(settings, "STORE_SITE_URL", "").rstrip("/")
    logo_url = getattr(settings, "STORE_EMAIL_LOGO_URL", "")
    
    from catalog.store_config import store_config

    cfg = store_config()
    store_whatsapp = cfg["whatsapp"]
    store_whatsapp_display = cfg["whatsapp_display"]

    context = {
        "order": order,
        "status_label": status_label,
        "status_emoji": config["emoji"],
        "status_message": config["message"],
        "site_url": site_url,
        "logo_url": logo_url,
        "year": datetime.now().year,
        "store_whatsapp": store_whatsapp,
        "store_whatsapp_display": store_whatsapp_display,
        "review_url": order_review_url(order) if order.status == "ENTREGADO" else "",
    }
    
    # Plain text fallback
    guide_line = ""
    if order.shipping_guide:
        carrier_part = f" ({order.carrier})" if order.carrier else ""
        guide_line = f"\nNúmero de guía: {order.shipping_guide}{carrier_part}\n"
        if order.tracking_url and order.tracking_url.startswith("http"):
            guide_line += f"Rastrea tu envío: {order.tracking_url}\n"
    
    detail_url = ""
    try:
        from django.urls import reverse
        path = reverse("orders:detail", kwargs={"access_token": order.access_token})
        detail_url = (site_url + path) if site_url else path
    except Exception:
        pass
    
    review_line = (
        f"\n¿Cómo te fue? Califica tu compra en 1 minuto: {context['review_url']}\n" if context["review_url"] else ""
    )
    text_body = (
        f"Hola {order.name},\n\n"
        f"{config['emoji']} {config['message']}\n"
        f"{guide_line}"
        f"\nVer detalles: {detail_url}\n"
        f"{review_line}"
        f"\n¿Necesitas ayuda? WhatsApp: https://wa.me/{store_whatsapp}\n"
        f"\nGracias por confiar en Pegasus Store.\n"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@pegasusstoremx.com")
    
    try:
        html_body = render_to_string("emails/order_status_change.html", context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[order.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
        
        logger.info("Status notification sent to %s for order #%s (%s)", order.email, order.pk, order.status)
        return True
    except Exception as exc:
        logger.error("Failed to send status notification for order #%s: %s", order.pk, exc)
        return False


def send_whatsapp_notification(order, old_status: str) -> bool:
    """
    Send a WhatsApp message via Twilio when order status changes.
    No-op (returns False) if Twilio credentials are not configured.
    """
    from django.conf import settings as _s
    sid      = getattr(_s, "TWILIO_ACCOUNT_SID", "")
    token    = getattr(_s, "TWILIO_AUTH_TOKEN", "")
    from_wa  = getattr(_s, "TWILIO_WHATSAPP_FROM", "")

    if not (sid and token and from_wa):
        return False  # Twilio no configurado — skip silencioso

    if not getattr(order, "phone", None):
        return False

    # Normalizar teléfono a E.164 (+52 y los 10 dígitos)
    from orders.forms import normalize_phone

    digits = normalize_phone(order.phone)
    if len(digits) != 10:
        return False
    phone = "+52" + digits

    site = getattr(_s, "STORE_SITE_URL", "").rstrip("/")
    detail_url = ""
    try:
        from django.urls import reverse
        path = reverse("orders:detail", kwargs={"access_token": order.access_token})
        detail_url = (site + path) if site else path
    except Exception:
        pass

    tracking_line = ""
    if getattr(order, "shipping_guide", None):
        carrier_part = f" ({order.carrier})" if getattr(order, "carrier", None) else ""
        tracking_line = f"\n\U0001f4cd Gu\u00eda: {order.shipping_guide}{carrier_part}"
        if getattr(order, "tracking_url", None) and order.tracking_url.startswith("http"):
            tracking_line += f"\n\U0001f50e Rastrear: {order.tracking_url}"

    detail_line = f"\nVer pedido: {detail_url}" if detail_url else ""

    messages_map = {
        "CONFIRMADO": (
            f"\u2705 *Pedido #{order.pk} confirmado*\n"
            f"Hola {order.name}, tu pedido est\u00e1 siendo preparado.{tracking_line}{detail_line}"
        ),
        "ENVIADO": (
            f"\U0001f69a *\u00a1Tu pedido #{order.pk} est\u00e1 en camino!*\n"
            f"Hola {order.name}, tu pedido ya fue despachado.{tracking_line}{detail_line}"
        ),
        "ENTREGADO": (
            f"\U0001f389 *Pedido #{order.pk} entregado*\n"
            f"Hola {order.name}, \u00a1tu pedido lleg\u00f3! Esperamos que lo disfrutes.\n"
            f"\u2b50 \u00bfC\u00f3mo te fue? Califica tu compra en 1 minuto: {order_review_url(order)}"
        ),
        "CANCELADO": (
            f"\u274c *Pedido #{order.pk} cancelado*\n"
            f"Hola {order.name}, tu pedido fue cancelado. "
            f"\u00bfNecesitas ayuda? Resp\u00f3ndenos aqu\u00ed."
        ),
    }

    msg_body = messages_map.get(order.status)
    if not msg_body:
        return False

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(
            body=msg_body,
            from_=f"whatsapp:{from_wa}",
            to=f"whatsapp:{phone}",
        )
        logger.info("WhatsApp sent to %s for order #%s (%s)", phone, order.pk, order.status)
        return True
    except ImportError:
        logger.warning("twilio no instalado — ejecuta: pip install twilio")
        return False
    except Exception as exc:
        logger.error("WhatsApp notification failed for order #%s: %s", order.pk, exc)
        return False


def notify_supplier_out_of_stock(order, unavailable_items: list[dict]) -> bool:
    """
    Avisa por WhatsApp al número de operaciones (OPS_WHATSAPP_NUMBER) cuando
    un pedido se crea con productos cuyo proveedor asignado no tenía stock.
    El pedido se guarda igual (needs_manual_supplier=True) para que el
    equipo lo reasigne a otro proveedor en Dropi y lo confirme a mano.
    No-op (retorna False) si Twilio o el número no están configurados.
    """
    from django.conf import settings as _s
    sid = getattr(_s, "TWILIO_ACCOUNT_SID", "")
    token = getattr(_s, "TWILIO_AUTH_TOKEN", "")
    from_wa = getattr(_s, "TWILIO_WHATSAPP_FROM", "")
    to_wa = getattr(_s, "OPS_WHATSAPP_NUMBER", "")

    if not (sid and token and from_wa and to_wa):
        return False

    phone = to_wa.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    site = getattr(_s, "STORE_SITE_URL", "").rstrip("/")
    detail_url = ""
    try:
        from django.urls import reverse
        path = reverse("orders:detail", kwargs={"access_token": order.access_token})
        detail_url = (site + path) if site else path
    except Exception:
        pass
    detail_line = f"\nVer pedido: {detail_url}" if detail_url else ""

    items_lines = "\n".join(
        f"• {it['name']} (dropi_id {it['dropi_id']}) x{it['quantity']}"
        for it in unavailable_items
    )

    msg_body = (
        f"⚠️ *Pedido #{order.pk} — proveedor sin stock*\n"
        f"Cliente: {order.name} {order.surname} · {order.phone}\n"
        f"Sin stock en el proveedor asignado:\n{items_lines}\n"
        f"El pedido quedó como Pendiente de confirmación pero NO se envió a Dropi. "
        f"Reasígnalo a otro proveedor y confírmalo a mano.{detail_line}"
    )

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(
            body=msg_body,
            from_=f"whatsapp:{from_wa}",
            to=f"whatsapp:{phone}",
        )
        logger.info("Alerta de stock enviada por WhatsApp para orden #%s", order.pk)
        return True
    except ImportError:
        logger.warning("twilio no instalado — ejecuta: pip install twilio")
        return False
    except Exception as exc:
        logger.error("Alerta de stock por WhatsApp falló para orden #%s: %s", order.pk, exc)
        return False


# ── On-demand sync helper ─────────────────────────────────────────────────────

_SYNC_COOLDOWN_SECONDS = 60  # 1 minuto entre syncs por orden

_SYNCABLE_STATUSES = {
    "PENDIENTE CONFIRMACION",
    "CONFIRMADO",
    "ENVIADO",
}


def try_sync_order(order) -> bool:
    """
    Consulta el estado más reciente en Dropi y actualiza la orden en lugar.

    - Solo actúa en órdenes activas con dropi_order_id.
    - Cooldown de 5 minutos por orden para no saturar la API.
    - Falla silenciosamente. Retorna True si el estado cambió.
    """
    from django.conf import settings as _settings

    if not getattr(_settings, "ORDER_ONDEMAND_SYNC", True):
        return False
    if not order.dropi_order_id:
        return False
    if order.status not in _SYNCABLE_STATUSES:
        return False

    from django.utils import timezone

    if order.last_dropi_sync is not None:
        elapsed = (timezone.now() - order.last_dropi_sync).total_seconds()
        if elapsed < _SYNC_COOLDOWN_SECONDS:
            return False

    try:
        from dropi_client.client import DropiClient

        client = DropiClient()
        data = client.get_order(order.dropi_order_id)
        changed, old_status = sync_order_from_dropi(order, data)
        if changed and order.status != old_status:
            try:
                notify_status_change(order, old_status)
            except Exception:
                pass
            try:
                send_whatsapp_notification(order, old_status)
            except Exception:
                pass
        return changed
    except Exception as exc:
        logger.warning("on-demand sync failed for order #%s: %s", order.pk, exc)
        return False


# ── Transportadora alternativa ────────────────────────────────────────────────
# La tienda no elige transportadora: Dropi usa la predeterminada de la cuenta
# para cada ciudad. Si esa no tiene "CON RECAUDO" en la ciudad (p. ej. Derocha
# Express en Popayán), Dropi rechaza la orden con "La ciudad no tiene
# habilitado el método de envío". Antes el pedido se cancelaba y había que
# rehacerlo a mano con otra transportadora (con Envía sí se entregó). Ahora se
# reintenta con las que la cuenta usa (IDs de distribution_company en Dropi).
# México: vacío hasta conocer las transportadoras de la cuenta de Dropi México
# y sus IDs (los de Colombia eran Envía=2, Coordinadora=5, Interrapidísimo=3).
# Con la lista vacía el rechazo se propaga y el pedido queda para crearlo a
# mano, en vez de reintentar con un ID que en México es otra empresa.
CARRIER_FALLBACKS: list[tuple[int, str]] = []


def is_carrier_unavailable_error(exc) -> bool:
    text = str(exc).lower()
    return "no tiene habilitado" in text or "habilitado el m" in text


def fold_shipping_into_prices(products: list[dict], total) -> None:
    """Sube el precio por unidad enviado a Dropi para que la suma de los
    productos sea `total` (productos + envío cobrado al cliente).

    Dropi ignora total_order: cobra contra entrega la suma de precio × cantidad
    de los productos. Con el envío solo en total_order, la transportadora
    cobraba los productos sin el envío (pedido #100: el cliente aceptó $63.800 y
    la orden quedó en $31.800, ganancia $450). La diferencia va a la línea con
    menos unidades; si no reparte exacto, se pierden menos pesos que unidades.
    """
    extra = int(round(float(total))) - int(round(sum(float(p["price"]) * int(p["quantity"]) for p in products)))
    if extra <= 0 or not products:
        return
    line = min(products, key=lambda p: int(p["quantity"]) or 1)
    line["price"] = float(line["price"]) + extra // (int(line["quantity"]) or 1)


def create_order_with_carrier_fallback(client, payload: dict) -> dict:
    """client.create_order(payload); si Dropi la rechaza solo porque la
    transportadora asignada no cubre la ciudad, reintenta con las alternativas.
    Cualquier otro error se propaga sin reintentar."""
    from dropi_client.exceptions import DropiAPIError

    try:
        return client.create_order(payload)
    except DropiAPIError as exc:
        if not is_carrier_unavailable_error(exc):
            raise
        last_error = exc
    for carrier_id, carrier_name in CARRIER_FALLBACKS:
        if carrier_name in str(last_error).upper():
            continue  # la que acaba de fallar
        attempt = dict(
            payload,
            distributionCompany={"id": carrier_id, "name": carrier_name},
            distribution_company_id=carrier_id,
        )
        try:
            response = client.create_order(attempt)
            logger.info("Orden %s creada en Dropi con %s tras rechazo de la transportadora predeterminada",
                        payload.get("shop_order_id"), carrier_name)
            return response
        except DropiAPIError as exc:
            if not is_carrier_unavailable_error(exc):
                raise
            last_error = exc
    raise last_error


def notify_manual_dropi_order(order, reason: str) -> bool:
    """Avisa por WhatsApp a operaciones (OPS_WHATSAPP_NUMBER) que un pedido
    quedó para crearlo a mano en Dropi. No-op si Twilio no está configurado:
    el pedido igual queda marcado en el admin ("⚠️ Crear a mano")."""
    from django.conf import settings as _s

    sid = getattr(_s, "TWILIO_ACCOUNT_SID", "")
    token = getattr(_s, "TWILIO_AUTH_TOKEN", "")
    from_wa = getattr(_s, "TWILIO_WHATSAPP_FROM", "")
    to_wa = getattr(_s, "OPS_WHATSAPP_NUMBER", "")
    if not (sid and token and from_wa and to_wa):
        return False
    phone = "".join(ch for ch in to_wa if ch.isdigit() or ch == "+")
    if not phone.startswith("+"):
        phone = "+" + phone
    items = ", ".join(f"{it.get('name', '')} x{it.get('quantity', 1)}" for it in (order.items or []))
    body = (
        f"⚠️ *Pedido #{order.pk} — crear a mano en Dropi*\n"
        f"Cliente: {order.name} {order.surname} · {order.phone} · {order.city}\n"
        f"Productos: {items}\n"
        f"Dropi respondió: {reason[:300]}"
    )
    try:
        from twilio.rest import Client

        Client(sid, token).messages.create(body=body, from_=f"whatsapp:{from_wa}", to=f"whatsapp:{phone}")
        return True
    except Exception:
        logger.exception("No se pudo avisar a operaciones del pedido #%s", order.pk)
        return False
