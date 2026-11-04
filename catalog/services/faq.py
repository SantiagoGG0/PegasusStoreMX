"""
Preguntas frecuentes de la tienda: una sola fuente para el inicio, la página
Confianza y el JSON-LD FAQPage (Google exige que el marcado coincida con el
texto visible, y antes cada página tenía su propia versión).
"""
from __future__ import annotations

from ..store_config import store_config
from .delivery import DELIVERY_ZONES_TEXT


def store_faq() -> list[dict]:
    cfg = store_config()
    legal_name = cfg["legal_name"] or cfg["name"]
    city, nit, hours = cfg["city"], cfg["nit"], cfg["support_hours"]
    identity = f"{legal_name}{f', RFC {nit}' if nit else ''}, con sede en {city}."
    support = f" Te atendemos por WhatsApp{f' ({hours})' if hours else ''}."
    return [
        {
            "q": "¿Pegasus Store es una tienda confiable?",
            "a": (
                f"Somos {identity} No te pedimos ningún pago por adelantado: pagas al repartidor "
                "cuando tienes el pedido en la mano, después de revisarlo. Cada envío tiene una "
                "guía que puedes rastrear en la paquetería." + support
            ),
        },
        {
            "q": "¿Realmente pago solo al recibir?",
            "a": (
                "Sí. El repartidor te entrega el pedido, lo revisas con él y pagas en ese momento en "
                "efectivo. No pedimos anticipos ni datos de tarjeta."
            ),
        },
        {
            "q": "¿Cuánto tarda mi pedido?",
            "a": (
                "Los pedidos de lunes a viernes salen el mismo día si los haces temprano; si no, al "
                f"día hábil siguiente. Después del despacho: {DELIVERY_ZONES_TEXT} En la ficha de "
                "cada producto ves la fecha estimada para tu ciudad."
            ),
        },
        {
            "q": "¿El envío tiene costo?",
            "a": (
                "La mayoría del catálogo tiene envío gratis a cualquier ciudad; lo ves marcado en "
                "cada producto. Cuando tiene costo, se calcula según tu ciudad y lo ves siempre "
                "antes de confirmar el pedido."
            ),
        },
        {
            "q": "¿Cómo sigo mi envío?",
            "a": (
                "Al despachar te enviamos por WhatsApp el número de guía. Puedes rastrearlo en la "
                "página de la transportadora o en la sección \"Mi pedido\" de la tienda."
            ),
        },
        {
            "q": "¿Y si el producto llega con falla o no es lo que pedí?",
            "a": (
                "Si lo notas al recibir, no lo recibes y no pagas nada. Si la falla aparece después, "
                "aplica la garantía de al menos 90 días (Ley Federal de Protección al Consumidor): escríbenos por WhatsApp y lo reparamos, lo "
                "cambiamos o te devolvemos el dinero, según corresponda, sin costo para ti. También "
                "tienes 5 días hábiles desde la entrega para revocar tu compra."
            ),
        },
        {
            "q": "¿Puedo cancelar mi pedido?",
            "a": (
                "Sí, sin costo, desde la página de tu pedido o por WhatsApp en los 15 minutos "
                "siguientes a confirmarlo, mientras no lo hayamos entregado a la transportadora. "
                "Te pedimos confirmar solo si vas a poder recibirlo."
            ),
        },
    ]


def faq_json_ld(items: list[dict]) -> dict:
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": item["q"], "acceptedAnswer": {"@type": "Answer", "text": item["a"]}}
            for item in items
        ],
    }
