"""
Datos de la tienda (razón social, RFC, contacto, horario, hora de corte…).

Fuente: la fila única de StoreSettings, editable en el admin. Cada campo
vacío cae al valor de settings (variables de entorno STORE_*), así el sitio
funciona igual antes de llenar la configuración.

    from catalog.store_config import store_config
    cfg = store_config()
    cfg["nit"], cfg["dispatch_cutoff_hour"]
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError

logger = logging.getLogger(__name__)

CACHE_KEY = "store_config_v1"
CACHE_SECONDS = 300
# Todo lo que depende de estos datos y se cachea aparte: se borra al guardar.
CACHE_KEYS = [CACHE_KEY, "trust_delivery_stats_v1"]

# campo del modelo → (setting, valor por defecto)
_FALLBACKS = {
    "name": ("STORE_NAME", "Pegasus Store"),
    "legal_name": ("STORE_LEGAL_NAME", ""),
    "nit": ("STORE_NIT", ""),
    "address": ("STORE_ADDRESS", ""),
    "city": ("STORE_CITY", "México"),
    "email": ("STORE_EMAIL", ""),
    "whatsapp": ("STORE_WHATSAPP", ""),
    "whatsapp_display": ("STORE_WHATSAPP_DISPLAY", ""),
    "support_hours": ("STORE_SUPPORT_HOURS", ""),
    "instagram": ("STORE_INSTAGRAM", ""),
    "whatsapp_channel_url": ("STORE_WHATSAPP_CHANNEL_URL", ""),
    "dispatch_cutoff_hour": ("STORE_DISPATCH_CUTOFF_HOUR", 14),
    "trust_min_delivered": ("TRUST_MIN_DELIVERED_TO_SHOW", 30),
}


def _from_settings() -> dict:
    return {field: getattr(settings, name, default) for field, (name, default) in _FALLBACKS.items()}


def store_config() -> dict:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    from .models import StoreSettings

    data = _from_settings()
    try:
        row = StoreSettings.objects.filter(pk=1).first()
    except DatabaseError:
        # Migración pendiente o base caída: el sitio sigue con los valores de settings.
        logger.exception("No se pudo leer StoreSettings; se usan los valores de settings")
        return data
    if row:
        for field in _FALLBACKS:
            value = getattr(row, field)
            if value not in (None, ""):
                data[field] = value.strip() if isinstance(value, str) else value
    cache.set(CACHE_KEY, data, CACHE_SECONDS)
    return data
