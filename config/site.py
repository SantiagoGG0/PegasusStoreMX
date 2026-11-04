"""URL pública canónica del sitio (STORE_SITE_URL).

Canonical, og:url, JSON-LD, sitemap y robots.txt deben apuntar siempre al
host canónico, no al host con el que llegó la petición (pegasusstoreco.com
o el dominio de DigitalOcean también responden). En desarrollo, sin
STORE_SITE_URL, se usa el host de la petición.
"""

from django.conf import settings


def site_base_url(request=None) -> str:
    """Esquema + host canónicos, sin barra final."""
    base = (getattr(settings, "STORE_SITE_URL", "") or "").rstrip("/")
    if base or request is None:
        return base
    return f"{request.scheme}://{request.get_host()}"


def absolute_url(request, path_or_url: str) -> str:
    """URL absoluta sobre el host canónico; las que ya son absolutas no cambian."""
    if not path_or_url:
        return ""
    value = str(path_or_url).strip()
    if value.startswith(("http://", "https://")):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return site_base_url(request) + value
