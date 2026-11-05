from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse, HttpResponsePermanentRedirect

from .admin_path import should_block_admin_path


class AdminPathGuardMiddleware:
    """403 en /admin (escaneos) y en bypass de path hacia ADMIN_URL."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._admin_slug = settings.ADMIN_URL.strip("/")

    def _candidate_paths(self, request) -> tuple[str, ...]:
        paths = [request.path, request.path_info]
        raw = request.META.get("RAW_URI") or request.META.get("REQUEST_URI")
        if raw:
            paths.append(raw.split("?", 1)[0])
        return tuple(dict.fromkeys(paths))

    def __call__(self, request):
        for path in self._candidate_paths(request):
            if should_block_admin_path(path, self._admin_slug):
                return HttpResponse("Forbidden", status=403, content_type="text/plain")
        return self.get_response(request)


def is_preview_host(request) -> bool:
    """Direcciones temporales (p. ej. monkfish-app-xxxx.ondigitalocean.app):
    Google no debe indexarlas, o el posicionamiento queda en un dominio que
    después hay que mudar."""
    host = request.get_host().split(":", 1)[0].lower()
    return host.endswith(tuple(getattr(settings, "NOINDEX_HOST_SUFFIXES", ())))


class PreviewHostNoindexMiddleware:
    """X-Robots-Tag: noindex en los hosts temporales. Va antes de la caché de
    páginas (que no distingue hosts) para calcularse en cada petición."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if is_preview_host(request):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response


class CanonicalHostMiddleware:
    """301 de los hosts antiguos (LEGACY_HOSTS) al host de STORE_SITE_URL,
    conservando ruta y query.

    - Solo GET/HEAD: un POST redirigido con 301 llega como GET y pierde el
      cuerpo (formularios, AJAX en curso).
    - Nunca toca CANONICAL_REDIRECT_EXEMPT_PATHS (webhook de Dropi), sea cual
      sea el host que Dropi tenga configurado.
    - Sin STORE_SITE_URL no hace nada, y nunca redirige un host a sí mismo.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _redirect_target(self, request):
        target = urlsplit(getattr(settings, "STORE_SITE_URL", "") or "")
        if not target.netloc or request.method not in ("GET", "HEAD"):
            return None
        if request.path.startswith(tuple(getattr(settings, "CANONICAL_REDIRECT_EXEMPT_PATHS", ()))):
            return None
        legacy = {h.strip().lower() for h in getattr(settings, "LEGACY_HOSTS", ()) if h.strip()}
        host = request.get_host().split(":", 1)[0].lower()
        if host not in legacy or host == target.netloc.lower():
            return None
        return f"{target.scheme or 'https'}://{target.netloc}{request.get_full_path()}"

    def __call__(self, request):
        url = self._redirect_target(request)
        if url:
            return HttpResponsePermanentRedirect(url)
        return self.get_response(request)


class ServerTimingMiddleware:
    """Cabecera Server-Timing con el tiempo que la app tarda en armar la
    respuesta y cuánto de eso fue base de datos (consultas y milisegundos).
    Se ve en las herramientas del navegador (pestaña Red → Tiempos) y con
    curl -I. No expone datos: solo duraciones."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time

        from django.db import connection

        stats = {"n": 0, "secs": 0.0}

        def track(execute, sql, params, many, context):
            start = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                stats["n"] += 1
                stats["secs"] += time.perf_counter() - start

        start = time.perf_counter()
        with connection.execute_wrapper(track):
            response = self.get_response(request)
        total_ms = (time.perf_counter() - start) * 1000
        response["Server-Timing"] = (
            f'app;dur={total_ms:.0f}, db;dur={stats["secs"] * 1000:.0f};desc="{stats["n"]} consultas"'
        )
        return response


class AnonymousPageCacheMiddleware:
    """Sirve desde caché (PAGE_CACHE_SECONDS) el HTML del inicio, categorías,
    fichas y páginas informativas a quien no tiene sesión: la mayoría de las
    visitas nuevas y todo Googlebot. En producción armar una categoría tomaba
    ~0,6 s en el servidor; desde caché, unos milisegundos.

    Reglas para no mostrarle a nadie datos de otro:
    - Solo GET/HEAD sin cookie de sesión ni de mensajes. Quien tiene carrito,
      ciudad elegida o cuenta tiene sesión y siempre recibe su página.
    - Solo se guardan respuestas 200 en HTML que no ponen cookies. Si la vista
      tocó la sesión o puso una cookie, esa respuesta no se guarda.
    - La clave incluye la URL completa y si es un buscador (el orden del
      catálogo para buscadores es fijo).
    """

    PREFIXES = ("/categoria/", "/producto/", "/confianza/", "/quienes-somos/", "/legal/")
    BLOCKING_COOKIES = ("messages",)

    def __init__(self, get_response):
        self.get_response = get_response

    def _eligible(self, request) -> bool:
        if request.method not in ("GET", "HEAD") or not getattr(settings, "PAGE_CACHE_SECONDS", 0):
            return False
        if request.path != "/" and not request.path.startswith(self.PREFIXES):
            return False
        cookies = request.COOKIES
        if settings.SESSION_COOKIE_NAME in cookies or any(name in cookies for name in self.BLOCKING_COOKIES):
            return False
        return True

    def _key(self, request) -> str:
        import hashlib

        from catalog.services.gallery_sync import is_bot

        raw = f"{request.get_full_path()}|{'bot' if is_bot(request) else 'web'}"
        return "page:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def __call__(self, request):
        if not self._eligible(request):
            return self.get_response(request)
        from django.core.cache import caches

        cache = caches["pages"]
        key = self._key(request)
        cached = cache.get(key)
        if cached is not None:
            content, headers = cached
            response = HttpResponse(content)
            for name, value in headers.items():
                response[name] = value
            response["X-Page-Cache"] = "HIT"
            return response

        response = self.get_response(request)
        cacheable = (
            response.status_code == 200
            and not response.streaming
            and not response.cookies
            and response.get("Content-Type", "").startswith("text/html")
        )
        if cacheable:
            # Cabeceras de la respuesta original (tipo, X-Frame-Options, Vary…),
            # menos las propias de cada petición.
            headers = {
                name: value for name, value in response.items()
                if name.lower() not in {"set-cookie", "server-timing", "x-page-cache", "content-length"}
            }
            cache.set(key, (response.content, headers), settings.PAGE_CACHE_SECONDS)
            response["X-Page-Cache"] = "MISS"
        return response
