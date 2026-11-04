import sys
from pathlib import Path

import dj_database_url
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Django admin URL (obscured path; override via ADMIN_URL in .env)
_admin_url = config('ADMIN_URL', default='panel-pegasus-interno/').strip().strip('/')
if not _admin_url:
    raise ImproperlyConfigured('ADMIN_URL cannot be empty.')
ADMIN_URL = f'{_admin_url}/'

# ── Dropi Integration ────────────────────────────────────────
DROPI_TOKEN = config('DROPI_TOKEN', default='')
# Tokens de integraciones adicionales (DROPI_TOKEN_2 … DROPI_TOKEN_9), solo
# para LEER catálogo: Dropi limita ~6 requests/min por token y catalog_worker
# reparte las galerías entre todos. Los pedidos siempre usan DROPI_TOKEN.
DROPI_READ_TOKENS = [DROPI_TOKEN] + [
    t for t in (config(f'DROPI_TOKEN_{i}', default='').strip() for i in range(2, 10)) if t
]
DROPI_BASE_URL = config('DROPI_BASE_URL', default='https://api.dropi.mx/integrations/')
DROPI_WEBHOOK_SECRET = config('DROPI_WEBHOOK_SECRET', default='')

# ── Gemini (Google AI) — generación de imágenes de producto ───
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_IMAGE_MODEL = config('GEMINI_IMAGE_MODEL', default='gemini-2.5-flash-image')

# ── Analytics ────────────────────────────────────────────────
GA4_MEASUREMENT_ID = config('GA4_MEASUREMENT_ID', default='')  # e.g. G-XXXXXXXXXX
# Cuenta de Google Ads de México ('AW-XXXXXXXXXX'). Vacía = no se carga la etiqueta.
GOOGLE_ADS_ID = config('GOOGLE_ADS_ID', default='')
# Proyecto de Microsoft Clarity de México. Vacío = no se carga.
CLARITY_PROJECT_ID = config('CLARITY_PROJECT_ID', default='')
META_PIXEL_ID = config('META_PIXEL_ID', default='')            # e.g. 1234567890123
TIKTOK_PIXEL_ID = config('TIKTOK_PIXEL_ID', default='')        # e.g. D982G9RC77UDPAPRK8Q0
# Acción de conversión "Compra" de Google Ads, formato 'AW-XXXX/LABEL'.
# Vacía = no se envía el evento de conversión (GA4 purchase sigue igual).
GOOGLE_ADS_PURCHASE_SEND_TO = config('GOOGLE_ADS_PURCHASE_SEND_TO', default='')

# ── Applications ─────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
    'django.contrib.postgres',
    # Third-party
    'storages',
    'cloudinary_storage',
    'cloudinary',
    # Local apps
    'dropi_client',
    'catalog',
    'cart',
    'orders',
    'pages',
    'accounts',
]

MIDDLEWARE = [
    'config.middleware.ServerTimingMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # Antes de la caché: una página guardada no debe servirse con 200 en un
    # host antiguo (pegasusstoreco.com sin www) en vez del 301 al canónico.
    'config.middleware.CanonicalHostMiddleware',
    'config.middleware.AnonymousPageCacheMiddleware',
    'config.middleware.AdminPathGuardMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serve static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                'catalog.context_processors.store',
                'config.context_processors.analytics',
                'config.context_processors.site',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database ──────────────────────────────────────────────────
# Si DATABASE_URL_REQUIRED=True (recomendado con Neon), nunca se usa SQLite por accidente.
DATABASE_URL = config('DATABASE_URL', default='').strip()
DATABASE_URL_REQUIRED = config('DATABASE_URL_REQUIRED', default=False, cast=bool)
if DATABASE_URL_REQUIRED and not DATABASE_URL:
    raise ImproperlyConfigured(
        'DATABASE_URL_REQUIRED=True pero DATABASE_URL está vacía. '
        'En Neon: Console → tu proyecto → Branch → Connect → copia la URI.'
    )

if DATABASE_URL:
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
    # El pooler de Neon (PgBouncer en modo transacción) no conserva los
    # cursores del lado del servidor entre transacciones: .iterator() falla
    # con 'cursor "_django_curs_..." does not exist'.
    if '-pooler' in DATABASE_URL:
        DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
    # Sin keepalives, una conexión que se cae (cambio de red, PC suspendido)
    # deja la consulta esperando indefinidamente; así falla en ~1 min.
    DATABASES['default'].setdefault('OPTIONS', {}).update({
        'connect_timeout': 10,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 3,
    })
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ── Auth validators ───────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalisation ──────────────────────────────────────
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# ── Static & Media ────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ── Media / Cloud storage ─────────────────────────────────────
# Django 5.2: STORAGES dict required — DEFAULT_FILE_STORAGE is ignored.
# Option A: Cloudinary. Set USE_CLOUDINARY=True + CLOUDINARY_URL env var.
#   Format: cloudinary://API_KEY:API_SECRET@CLOUD_NAME
# Option B: S3/DO Spaces. Set USE_S3=True + AWS_* vars.
USE_CLOUDINARY = config('USE_CLOUDINARY', default=False, cast=bool)
if not USE_CLOUDINARY:
    import os as _os
    USE_CLOUDINARY = _os.environ.get('USE_CLOUDINARY', '').upper() in ('TRUE', '1', 'YES')
USE_S3 = config('USE_S3', default=False, cast=bool)

_WHITENOISE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

if USE_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader
    # Support both CLOUDINARY_URL (preferred) and separate vars
    _cloudinary_url = config('CLOUDINARY_URL', default='')
    if _cloudinary_url:
        # cloudinary SDK auto-configures from CLOUDINARY_URL env var
        cloudinary.config(cloudinary_url=_cloudinary_url)
    else:
        cloudinary.config(
            cloud_name=config('CLOUDINARY_CLOUD_NAME'),
            api_key=config('CLOUDINARY_API_KEY'),
            api_secret=config('CLOUDINARY_API_SECRET'),
        )
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': cloudinary.config().cloud_name,
        'API_KEY':    cloudinary.config().api_key,
        'API_SECRET': cloudinary.config().api_secret,
    }
    STORAGES = {
        'default':     {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'},
        'staticfiles': {'BACKEND': _WHITENOISE},
    }
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
elif USE_S3:
    AWS_ACCESS_KEY_ID       = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY   = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME      = config('AWS_S3_REGION_NAME', default='nyc3')
    AWS_S3_CUSTOM_DOMAIN    = config('AWS_S3_CUSTOM_DOMAIN', default='')
    AWS_DEFAULT_ACL         = 'public-read'
    AWS_S3_FILE_OVERWRITE   = False
    AWS_QUERYSTRING_AUTH    = False
    _spaces_endpoint = config('AWS_S3_ENDPOINT_URL', default='')
    if _spaces_endpoint:
        AWS_S3_ENDPOINT_URL = _spaces_endpoint
    _custom = AWS_S3_CUSTOM_DOMAIN
    if _custom:
        MEDIA_URL = f'https://{_custom}/'
    elif _spaces_endpoint:
        MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.{AWS_S3_REGION_NAME}.digitaloceanspaces.com/'
    else:
        MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'
    STORAGES = {
        'default':     {'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage'},
        'staticfiles': {'BACKEND': _WHITENOISE},
    }
else:
    MEDIA_URL  = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    STORAGES = {
        'default':     {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': _WHITENOISE},
    }

# Tests: el storage con manifiesto exige haber corrido collectstatic y que el
# manifiesto esté al día (en local suele estar viejo y en CI no existe), y
# falla en cada {% static %}. Los tests no necesitan nombres con hash.
# Ficha de producto: trae la galería completa de Dropi la primera vez que
# alguien la abre (catalog.services.gallery_sync.ensure_gallery_on_view).
GALLERY_ON_VIEW = config('GALLERY_ON_VIEW', default=True, cast=bool)
# En segundo plano: la ficha no espera a Dropi (Core Web Vitals).
GALLERY_ON_VIEW_ASYNC = config('GALLERY_ON_VIEW_ASYNC', default=True, cast=bool)

if len(sys.argv) > 1 and sys.argv[1] == 'test':
    STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}
    GALLERY_ON_VIEW = False  # los tests no llaman a Dropi
    NAV_CACHE_SECONDS = 0    # cada test arma su propio menú

# ── Cart session key ──────────────────────────────────────────
CART_SESSION_ID = 'cart'

# ── Catalog home sections (extensible; enable in settings when ready) ──
# hero/trust_tiles/category_tiles/favorites/how_it_works/for_you/testimonials/cta_band
# only render on the plain "/" landing state (no category, no search).
# catalog_header/catalog_grid only render once a category or search is active —
# that's the paginated listing/results view.
CATALOG_HOME_SECTIONS = [
    # Orden de venta: propuesta → productos → categorías → cómo funciona →
    # prueba social → dudas. El marquee (frases repetidas) quedó apagado.
    {"id": "hero", "enabled": True},
    {"id": "featured", "enabled": True},
    {"id": "category_tiles", "enabled": True},
    {"id": "how_it_works", "enabled": True},
    {"id": "social_proof", "enabled": True},
    {"id": "faq", "enabled": True},
    {"id": "marquee", "enabled": False},
    {"id": "catalog_header", "enabled": True},
    {"id": "catalog_grid", "enabled": True},
]

# ── Store identity (buyer trust) ──────────────────────────────
STORE_NAME = config("STORE_NAME", default="Pegasus Store")
STORE_LEGAL_NAME = config("STORE_LEGAL_NAME", default="")
STORE_ADDRESS = config("STORE_ADDRESS", default="")
STORE_CITY = config("STORE_CITY", default="México")
STORE_EMAIL = config("STORE_EMAIL", default="")
STORE_WHATSAPP = config("STORE_WHATSAPP", default="")
STORE_WHATSAPP_DISPLAY = config("STORE_WHATSAPP_DISPLAY", default="")
# Identidad visible (LFPC art. 76 bis: razón social, RFC,
# dirección, teléfono y correo). Vacíos = no se muestran; nunca inventar.
# Todos los STORE_* de esta sección se editan en el admin (Catálogo →
# Configuración de la tienda); estos valores solo se usan si el campo del
# admin está vacío. Ver catalog/store_config.py.
STORE_NIT = config("STORE_NIT", default="")
# Horario real de atención por WhatsApp (p. ej. "Lunes a sábado, 8 a. m. a 6 p. m.").
# Vacío = no se promete horario.
STORE_SUPPORT_HOURS = config("STORE_SUPPORT_HOURS", default="")
STORE_INSTAGRAM = config("STORE_INSTAGRAM", default="")
# Enlace a un canal de WhatsApp real (whatsapp.com/channel/…). Vacío = el
# inicio ofrece escribir por WhatsApp en vez de "unirse al canal".
STORE_WHATSAPP_CHANNEL_URL = config("STORE_WHATSAPP_CHANNEL_URL", default="")
# Hora (0-23, Ciudad de México) hasta la que un pedido de lunes a viernes sale el mismo
# día; después, o en fin de semana, la ficha dice "el próximo día hábil".
STORE_DISPATCH_CUTOFF_HOUR = config("STORE_DISPATCH_CUTOFF_HOUR", default=14, cast=int)
# Cifras de confianza (pedidos entregados, ciudades) se muestran solo desde
# este mínimo, para no exhibir números que asusten más de lo que ayudan.
TRUST_MIN_DELIVERED_TO_SHOW = config("TRUST_MIN_DELIVERED_TO_SHOW", default=30, cast=int)
# Número interno que recibe la alerta cuando un pedido se crea con un producto
# que su proveedor de Dropi tiene agotado (para reasignarlo a mano a otro
# proveedor). Distinto de STORE_WHATSAPP, que es el soporte al cliente.
OPS_WHATSAPP_NUMBER = config("OPS_WHATSAPP_NUMBER", default="")
# URL canónica del sitio, sin barra final (producción: el dominio de México con www).
# La usan canonical, og:url, sitemap, JSON-LD, robots.txt y la redirección de
# hosts antiguos. Vacía (desarrollo) = se usa el host de cada petición.
STORE_SITE_URL = config("STORE_SITE_URL", default="").strip().rstrip("/")
# Hosts que responden 301 hacia el host de STORE_SITE_URL (solo GET/HEAD).
LEGACY_HOSTS = config(
    "LEGACY_HOSTS",
    default="",
    cast=Csv(),
)
# Rutas que nunca se redirigen: las llama Dropi y no deben depender del host.
CANONICAL_REDIRECT_EXEMPT_PATHS = ("/pedidos/webhook/",)
STORE_EMAIL_LOGO_URL = config("STORE_EMAIL_LOGO_URL", default="")  # URL logo para emails

# ── Twilio WhatsApp (opcional) ────────────────────────────────
# Configura estas variables en .env para activar mensajes WhatsApp
# al cliente cuando su pedido cambia de estado.
# TWILIO_ACCOUNT_SID  = ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# TWILIO_AUTH_TOKEN   = tu_auth_token
# TWILIO_WHATSAPP_FROM = +14155238886  (número sandbox o aprobado)
TWILIO_ACCOUNT_SID   = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN    = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_WHATSAPP_FROM = config("TWILIO_WHATSAPP_FROM", default="")

# Payment: hide prepaid until a real gateway is integrated
ENABLE_PREPAID_PAYMENT = config("ENABLE_PREPAID_PAYMENT", default=False, cast=bool)

# Real testimonials only — list of {"name", "city", "text", "rating"} dicts.
# The home section auto-hides when this is empty (see catalog/sections.py
# _section_testimonials), so leave it empty until there are real reviews to
# quote here.
STORE_TESTIMONIALS = []

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Carrito — reglas Dropi por proveedor
CART_MAX_SUPPLIERS = 2
CART_SUGGESTED_PRODUCTS_LIMIT = 48

# ── Pricing ──────────────────────────────────────────────────
# price = max(suggested_price, cost × PRODUCT_MARKUP_FACTOR, cost + MIN_PRODUCT_PROFIT)
PRODUCT_MARKUP_FACTOR = 1.8      # multiplier over cost as price floor
MIN_PRODUCT_PROFIT = 25          # MXN — minimum margin per product

# ── Shipping zones (México) ──────────────────────────────────
# Cotización real de Dropi México, contra entrega (2026-11-04), igual para
# Mexicali y Ciudad de México: Quality-post $149, Veloces $162, Tiui $170,
# Coordi $188 (Ampm y Afimex sin tarifa). La tarifa no depende del destino y
# la tienda no elige la paquetería (Dropi usa la predeterminada de la cuenta),
# así que se toma la más cara para no perder en ninguna guía. Si en Dropi se
# fija una paquetería predeterminada, bajar a su tarifa.
# Cost per guide (one guide per supplier per order)
SHIPPING_ZONE_A_COST = 188   # Zonas metropolitanas (CDMX, Guadalajara, Monterrey...)
SHIPPING_ZONE_B_COST = 188   # Resto de ciudades con cobertura contra entrega
SHIPPING_ZONE_C_COST = 250   # Zonas remotas de la lista (hoy ninguna; estimado)

# ── Net profitability rule ──────────────────────────────────────
# Used by Product.expected_net_profit / Product.is_profitable and by
# `manage.py apply_profitability_rule` to flag which products are actually
# worth keeping published. Model (see catalog/models.py for the full
# derivation): the checkout shipping engine (cart/shipping.py) already
# guarantees the store never loses money on a *delivered* order — either the
# margin covers the guide cost and shipping is "free", or the customer is
# charged the shortfall and the store breaks even. The real risk is a
# rejected COD order: no revenue collected, but the outbound guide cost is
# already spent. COD_REJECTION_RATE is a first estimate — replace it with
# your real rejection rate from Dropi order history once you have enough
# volume to compute one (see orders.Order.status = CANCELADO history).
# PROVISIONAL: en Colombia el dato real fue 8% (se usaba 10%). En México el
# contra entrega suele rechazarse más: se arranca con 20% y se recalcula con
# los primeros pedidos cerrados.
COD_REJECTION_RATE = config("COD_REJECTION_RATE", default=0.20, cast=float)
# Con el piso por costo (PRICING_MIN_GAIN_LADDER) el mínimo es "no perder
# plata en promedio" (0); súbelo para exigir más a Product.is_profitable.
MIN_NET_PROFIT = config("MIN_NET_PROFIT", default=0, cast=int)  # MXN — expected net profit floor per unit

# Rule 1 (ceiling): pesos, not percentage. shipping_gap = max(0, guide_cost -
# margin) is what the buyer would see charged as shipping at checkout (Zone
# A, the cheapest case) when the margin doesn't cover the guide. Above this
# ceiling, no price adjustment fixes it alone — it needs a combo with
# another product to spread the fixed guide cost. Starting value is the
# midpoint of the $15k-$20k range flagged as a first estimate — tune with
# real per-city shipping data once available.
SHIPPING_CEILING = config("SHIPPING_CEILING", default=130, cast=int)  # MXN

# Rule 2 (below ceiling): both floors must hold, not just one — a product
# can look fine on either metric alone and still be a bad bet (e.g. 100%
# margin on an $8,000 cost has no real pesos to absorb shipping; huge peso
# margin on an inflated cost can hide a razor-thin %).
MIN_MARGIN_PERCENT = config("MIN_MARGIN_PERCENT", default=0.30, cast=float)  # 30% over Dropi cost

# What a rejected COD order costs the store. Dropi doesn't charge the return
# leg, so the default is only the outbound guide (Zone A). Set it to 0 if
# Dropi doesn't charge the outbound guide either on a rejected order.
COD_REJECTION_LOSS = config("COD_REJECTION_LOSS", default=SHIPPING_ZONE_A_COST, cast=int)  # MXN

# ── Pricing engine (catalog/services/pricing.py + cart/shipping.py) ──────────
# Piso: ganancia mínima por unidad entregada según el costo del producto.
# Tramos (costo menor a, ganancia fija, % del costo); se usa el mayor de los
# dos. El último tramo no tiene tope (None). Si el margen no alcanza para
# regalar el envío (margen < guía + piso), el cliente paga la diferencia.
PRICING_MIN_GAIN_LADDER = [
    # PROVISIONAL: la escalera de Colombia convertida (~215 COP por MXN) y
    # redondeada. Recalibrar con las ventas reales de México.
    (50, 35, 1.00),       # < $50: al menos el costo, mínimo $35
    (120, 55, 0),         # $50 - $120
    (250, 85, 0),         # $120 - $250
    (500, 120, 0),        # $250 - $500
    (None, 120, 0.15),    # > $500: 15% del costo
]
# Techo: nunca más de este factor sobre el sugerido de Dropi, salvo que el
# piso lo exija. En productos caros el comprador compara más: tope más bajo.
PRICING_MAX_OVER_SUGGESTED = config("PRICING_MAX_OVER_SUGGESTED", default=1.3, cast=float)
PRICING_EXPENSIVE_FROM = 500  # MXN de costo
PRICING_MAX_OVER_SUGGESTED_EXPENSIVE = config("PRICING_MAX_OVER_SUGGESTED_EXPENSIVE", default=1.1, cast=float)
PRICING_DEFAULT_PROFILE = {"markup": 1.8, "weight": 1.0}
# Claves = Category.dropi_id sin el prefijo "store:". weight = prioridad en el
# ranking del catálogo (categorías prioritarias del negocio > 1).
PRICING_CATEGORY_PROFILES = {
    "belleza":          {"markup": 1.9, "weight": 1.5},
    "tecnologia":       {"markup": 1.7, "weight": 1.5},
    "bienestar_intimo": {"markup": 2.0, "weight": 1.4},
    "salud_bienestar":  {"markup": 1.9, "weight": 1.4},
    "fiesta_pinateria": {"markup": 2.2, "weight": 0.6},
}

# ── Gallery / image quality ──────────────────────────────────────────────────
# Productos con menos imágenes válidas que este mínimo bajan en el ranking.
CATALOG_MIN_IMAGES = config("CATALOG_MIN_IMAGES", default=2, cast=int)
# Debajo de este precio un producto no se vende solo (la guía cuesta varias
# veces más) y en la vitrina parece un error ("$900"): no se publica.
CATALOG_MIN_PRICE = config("CATALOG_MIN_PRICE", default=25, cast=int)  # MXN

# ── Email ─────────────────────────────────────────────────────
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Pegasus Store <noreply@pegasusstore.co>')

# ── Security headers (always) ────────────────────────────────
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ── Password reset link expires in 1 day ────────────────────
PASSWORD_RESET_TIMEOUT = 86400  # 1 day (Django default = 3 days)

# ── CSRF trusted origins ─────────────────────────────────────
# Add your production domain: CSRF_TRUSTED_ORIGINS=https://tudominio.co
_csrf_origins_raw = config('CSRF_TRUSTED_ORIGINS', default='')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_raw.split(',') if o.strip()]

# ── Rate limiting (django-ratelimit) ─────────────────────────
RATELIMIT_USE_CACHE = 'ratelimit'
# Caché por defecto en archivos (CACHE_DIR, /tmp en el contenedor): la
# comparten los procesos de gunicorn y sobrevive a que gunicorn los recicle
# (--max-requests). En memoria (LocMem) cada proceso tenía su propia copia y
# la perdía cada ~1.000 visitas, así que menú, sitemaps y "lo más pedido" se
# recalculaban seguido, y guardar la configuración de la tienda en el admin
# solo limpiaba la caché de un proceso. Las pruebas siguen en memoria.
import os as _os
import sys as _sys
import tempfile as _tempfile

_TESTING = len(_sys.argv) > 1 and _sys.argv[1] == 'test'
CACHE_DIR = config('CACHE_DIR', default=_os.path.join(_tempfile.gettempdir(), 'pegasus-cache'))
CACHES = {
    'default': (
        {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
        if _TESTING else
        {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': CACHE_DIR,
            'TIMEOUT': 300,
            'OPTIONS': {'MAX_ENTRIES': 5000},
        }
    ),
    # HTML de páginas para visitantes sin sesión (AnonymousPageCacheMiddleware).
    # Aparte, con su propio tope, para no desplazar lo demás ni llenar el disco.
    'pages': (
        {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'pages'}
        if _TESTING else
        {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': _os.path.join(CACHE_DIR, 'pages'),
            'OPTIONS': {'MAX_ENTRIES': 1500},
        }
    ),
    'ratelimit': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'ratelimit',
    },
}

# Al abrir un pedido (confirmación, detalle), consultar su estado en Dropi.
# Apagado en las pruebas: si no, cada prueba de esas páginas llamaba a la API
# real de Dropi (y tardaba minutos cuando Dropi limitaba las consultas).
ORDER_ONDEMAND_SYNC = not _TESTING

# Minutos que una página se sirve desde caché a visitantes sin sesión. Un
# cambio de precio o stock tarda como máximo esto en verse. 0 = apagado.
# Apagado en las pruebas (cada prueba arma sus propios datos en las mismas URL).
PAGE_CACHE_SECONDS = 0 if _TESTING else config('PAGE_CACHE_SECONDS', default=300, cast=int)

# ── Logging ───────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', default='WARNING'),
            'propagate': False,
        },
        'orders': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'dropi_client': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'catalog': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ── Security (production) ─────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    if ADMIN_URL == 'admin/':
        raise ImproperlyConfigured(
            'ADMIN_URL no puede ser "admin/" en producción. Usa una ruta personalizada.'
        )
    if not DROPI_WEBHOOK_SECRET:
        raise ImproperlyConfigured(
            "DROPI_WEBHOOK_SECRET es obligatorio en producción (DEBUG=False)."
        )
    if not DROPI_TOKEN:
        raise ImproperlyConfigured(
            "DROPI_TOKEN es obligatorio en producción (DEBUG=False). "
            "Sin él todos los pedidos fallarán al enviarse a Dropi."
        )
    if not STORE_SITE_URL or STORE_SITE_URL.split("://", 1)[-1] in LEGACY_HOSTS:
        import warnings
        warnings.warn(
            "STORE_SITE_URL debe ser la URL canónica (https://www.<dominio>) en producción: "
            "sin ella canonical y sitemap usan el host de cada petición y no se "
            "redirigen los hosts antiguos.",
            RuntimeWarning,
            stacklevel=2,
        )
    if not EMAIL_HOST_PASSWORD:
        import warnings
        warnings.warn(
            "EMAIL_HOST_PASSWORD no está configurado. Los emails de confirmación fallarán silenciosamente.",
            RuntimeWarning,
            stacklevel=2,
        )
    # DO App Platform already handles HTTPS at the proxy level
    # SECURE_SSL_REDIRECT causes redirect loops behind DO's proxy
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
