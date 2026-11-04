"""Utilidades SEO (funciones puras + helpers sin side-effects)."""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import date, timedelta

from django.utils.text import Truncator

from config.site import absolute_url

SITE_NAME = "Pegasus Store"

# Marcas reales de productos que vendemos originales, para el "brand" de los
# datos estructurados y del feed: con "Pegasus Store" como marca de todo, Google
# no asocia la ficha con búsquedas como "selvia ajenjo" o "beevana precio".
# A propósito no están las marcas que el catálogo trae como réplica (Nike,
# Lacoste, Apple…): declararlas como marca sería peor que no hacerlo.
KNOWN_BRANDS = (
    "Selvia", "Perfectx", "Beevana", "Oveallgo", "Herbcure", "Herbacure", "Drenazan", "Clear Zal", "Luminiix",
    "Receloviix", "Allicarp", "Mama Bear", "Nawhi", "Windboss", "Zupi", "Mercilen", "Amexol", "Gfouk",
    "Rainbow Light", "Sureboy", "Ilcesan", "Fumarex", "Tinnidrop", "Muqi", "Karsell", "Bioaqua", "Circuvena",
    "Toenail Plus", "Fungikill", "Sokany",
)
TITLE_MAX = 60
DESCRIPTION_MAX = 155

# Emojis, pictogramas y símbolos decorativos que Dropi trae en los textos
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000200D\U000020E3\U00002190-\U000021FF\U00002700-\U000027BF\U0000231A-\U0000231B"
    "•▪●★☆✔✖✨]+"
)
# Rótulos de plantilla de los proveedores que no aportan nada en un snippet
_BOILERPLATE = re.compile(
    r"(descripci[oó]n del producto|caracter[ií]sticas( principales)?|especificaciones|"
    r"beneficios|modo de uso|contenido del paquete|incluye)\s*:?",
    re.I,
)


def encode_url(url: str) -> str:
    """Codifica espacios y caracteres especiales del path (Dropi sube fotos como
    "WhatsApp Image 2025-11-25 at 5.03.06 PM.jpeg"): Google Merchant y los
    sitemaps rechazan URLs con espacios."""
    from urllib.parse import quote, urlsplit, urlunsplit

    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/:@!$&'()*+,;=%"), parts.query, parts.fragment))


def _absolute_media_url(request, url: str) -> str:
    if not url:
        return ""
    return encode_url(absolute_url(request, url))


_TAGS = re.compile(r"<[^>]*>")
_CAPS_HEADING = re.compile(r"^[A-ZÁÉÍÓÚÑÜ0-9][A-ZÁÉÍÓÚÑÜ0-9 ,.\-–—/&+%x]{12,}?(?=\s+[A-ZÁÉÍÓÚÑÜ]?[a-záéíóúñü])")


def clean_text(text: str) -> str:
    """Texto plano limpio: sin HTML, emojis, rótulos de plantilla ni espacios de más.

    Quita etiquetas con una expresión regular (strip_tags de Django es ~10×
    más lento y el feed de Merchant limpia 40.000 descripciones)."""
    text = html.unescape(_TAGS.sub(" ", text or ""))
    text = _EMOJI.sub(" ", text)
    text = _BOILERPLATE.sub(" ", text)
    text = re.sub(r"[_*#=~|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -–—:;,.")


def nice_name(name: str) -> str:
    """Nombres en MAYÚSCULAS de Dropi → tipo oración ("Aceite de jengibre x1")."""
    name = clean_text(name).strip(" \"'“”«»")
    letters = [c for c in name if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        name = name.lower()
        name = name[:1].upper() + name[1:]
    return name


def product_name(product) -> str:
    """Nombre visible del producto (Product.shown_name: sin cortes de Dropi ni
    etiquetas internas); objetos sin esa propiedad usan nice_name."""
    shown = getattr(product, "shown_name", None)
    return clean_text(shown) if shown else nice_name(product.name)


def product_text(product, limit: int = 0) -> str:
    """Texto del producto para metas, JSON-LD y feed: el propio
    (description_unique) o el del proveedor sin su garantía ni contactos
    (description_sanitizer.clean_description_for_display). limit recorta el
    texto crudo antes de limpiarlo (el feed procesa 40.000 productos)."""
    from .services.content_generation import is_generated_description
    from .services.description_sanitizer import clean_description_for_display

    own = (getattr(product, "description_unique", "") or "").strip()
    if own and not is_generated_description(own):
        return clean_text(own)

    raw = product.description or ""
    if limit:
        raw = raw[:limit]
    return clean_text(" ".join(clean_description_for_display(raw)))


def format_cop(value) -> str:
    """$1,299 (en México el separador de miles es la coma). Conserva el nombre
    del proyecto de Colombia para que los arreglos se porten igual."""
    return "$" + f"{int(round(float(value or 0))):,}"


def generate_seo_title(product) -> str:
    curated = (getattr(product, "meta_title", "") or "").strip()
    if curated:
        return curated
    name = product_name(product)
    for suffix in (" | Pago contra entrega | " + SITE_NAME, " | " + SITE_NAME):
        if len(name) + len(suffix) <= TITLE_MAX:
            return name + suffix
    room = TITLE_MAX - len(" | " + SITE_NAME)
    return Truncator(name).chars(room, truncate="…") + " | " + SITE_NAME


def generate_meta_description(product, max_length: int = DESCRIPTION_MAX) -> str:
    curated = (getattr(product, "meta_description", "") or "").strip()
    if curated:
        return Truncator(curated).chars(max_length, truncate="…")
    name = product_name(product)
    shipping = "envío gratis" if getattr(product, "likely_free_shipping", False) else "envío a todo México"
    lead = f"{name} por {format_cop(product.price)}, con pago contra entrega y {shipping}."
    detail = product_text(product)
    if detail.lower().startswith(name.lower()):
        detail = detail[len(name):].strip(" -–—:;,.")
    # Encabezado en MAYÚSCULAS al inicio ("ACEITE DE JENGIBRE – TERAPIA …"):
    # repite el nombre que ya va al principio del snippet.
    heading = _CAPS_HEADING.match(detail)
    if heading:
        detail = detail[heading.end():].strip(" -–—:;,.")
    text = f"{lead} {detail}" if detail else lead
    return Truncator(text).chars(max_length, truncate="…")


def generate_og_tags(product, request) -> list[tuple[str, str]]:
    description = generate_meta_description(product)
    page_url = absolute_url(request, product.get_absolute_url())
    image_url = _absolute_media_url(request, product.display_main_image)
    tags: list[tuple[str, str]] = [
        ("og:type", "product"),
        ("og:title", product_name(product)),
        ("og:description", description),
        ("og:url", page_url),
    ]
    if image_url:
        tags.append(("og:image", image_url))
    return tags


def product_image_urls(product, request, limit: int = 10) -> list[str]:
    urls = []
    custom = list(product.custom_images.all()) if hasattr(product, "custom_images") else []
    for ci in custom:
        if ci.image:
            urls.append(_absolute_media_url(request, ci.image.url))
    if not urls:
        for img in product.images or []:
            raw = img.get("url") if isinstance(img, dict) else str(img)
            if raw:
                urls.append(_absolute_media_url(request, raw))
    seen, unique = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            unique.append(u)
    return unique[:limit]


# Devoluciones (ver /legal/devoluciones/): retracto de 5 días hábiles desde la
# entrega, el comprador asume el transporte de la devolución.
RETURN_POLICY = {
    "@type": "MerchantReturnPolicy",
    "applicableCountry": "MX",
    "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
    "merchantReturnDays": 5,
    "returnMethod": "https://schema.org/ReturnByMail",
    "returnFees": "https://schema.org/ReturnFeesCustomerResponsibility",
}

def mainland_regions() -> list[str]:
    """Estados (ISO 3166-2, sin "MX-") donde ningún municipio cae en la zona C
    de cart/shipping.py. Hoy la zona C está vacía: son los 32."""
    from cart.mexico_geo import states
    from cart.shipping import states_with_zone_c

    remote = states_with_zone_c()
    return [code for code, _ in states() if code not in remote]


def free_shipping_outside_remote_zones(product) -> bool:
    """Una unidad deja margen para regalar la guía de zona B (la más cara
    fuera de las zonas remotas) y conservar la ganancia mínima."""
    from django.conf import settings

    from catalog.services.pricing import min_gain

    try:
        margin = product.price - product.cost
    except TypeError:
        return False
    return product.cost > 0 and margin >= settings.SHIPPING_ZONE_B_COST + min_gain(product.cost)


DELIVERY_TIME = {
    "@type": "ShippingDeliveryTime",
    "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "DAY"},
    "transitTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 5, "unitCode": "DAY"},  # services/delivery.DELIVERY_SPANS
}


def breadcrumb_json_ld(request, crumbs: list[tuple[str, str]]) -> dict:
    """crumbs = [(nombre, url relativa o absoluta), …] en orden."""
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": absolute_url(request, url)}
            for i, (name, url) in enumerate(crumbs, 1)
        ],
    }


def category_slug(dropi_id: str) -> str:
    """"store:salud_bienestar" → "salud-bienestar"."""
    return str(dropi_id or "").split(":", 1)[-1].replace("_", "-")


def category_dropi_id(slug: str) -> str:
    """"salud-bienestar" → "store:salud_bienestar"."""
    return "store:" + slug.replace("-", "_")


def category_path(dropi_id: str) -> str:
    """URL limpia de una categoría: /categoria/belleza/. Solo las categorías
    de la tienda ("store:…"); otras conservan la URL con parámetro."""
    if not str(dropi_id or "").startswith("store:"):
        return f"/?category={dropi_id}"
    return f"/categoria/{category_slug(dropi_id)}/"


def category_url(category) -> str:
    return category_path(category.dropi_id)


def _brand_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " " + " ".join(re.sub(r"[^a-z0-9]+", " ", text).split()) + " "


# "Clear Zal" también aparece escrito "CLEARZAL", "Toenail Plus" como "TOENAILPLUS".
_BRAND_KEYS = tuple(
    (keys, brand)
    for brand in KNOWN_BRANDS
    for keys in [{_brand_key(brand), f" {_brand_key(brand).replace(' ', '')} "}]
)


def product_brand(product) -> str:
    """Marca real si el nombre trae una de KNOWN_BRANDS; si no, la tienda."""
    names = _brand_key(getattr(product, "name", "")) + _brand_key(getattr(product, "display_name", ""))
    for keys, brand in _BRAND_KEYS:
        if any(key in names for key in keys):
            return brand
    return SITE_NAME


def generate_json_ld(product, request, collection=None) -> dict:
    description = product_text(product) or product_name(product)
    availability = (
        "https://schema.org/InStock"
        if product.stock > 0 and product.is_active
        else "https://schema.org/OutOfStock"
    )
    product_url = absolute_url(request, product.get_absolute_url())
    offer: dict = {
        "@type": "Offer",
        "url": product_url,
        "priceCurrency": "MXN",
        "price": str(product.price),
        # Desde cuándo rige el precio (Search Console lo pide en "Fichas de
        # comerciantes"): la última actualización del producto.
        "validFrom": (product.last_synced.date() if getattr(product, "last_synced", None) else date.today()).isoformat(),
        "priceValidUntil": (date.today() + timedelta(days=30)).isoformat(),
        "availability": availability,
        "itemCondition": "https://schema.org/NewCondition",
        "seller": {"@type": "Organization", "name": SITE_NAME},
        "hasMerchantReturnPolicy": RETURN_POLICY,
    }
    # El envío depende de la ciudad y del carrito: solo se declara donde es
    # gratis seguro, para que Google muestre "Envío gratis" y coincida con el
    # checkout. Gratis en todo el país (también zonas remotas) → todo CO;
    # gratis hasta la zona B → todos los departamentos menos los remotos.
    destination = None
    if getattr(product, "likely_free_shipping", False):
        destination = {"@type": "DefinedRegion", "addressCountry": "MX"}
    elif free_shipping_outside_remote_zones(product):
        destination = {"@type": "DefinedRegion", "addressCountry": "MX", "addressRegion": mainland_regions()}
    if destination:
        offer["shippingDetails"] = {
            "@type": "OfferShippingDetails",
            "shippingRate": {"@type": "MonetaryAmount", "value": "0", "currency": "MXN"},
            "shippingDestination": destination,
            "deliveryTime": DELIVERY_TIME,
        }
    data: dict = {
        "@type": "Product",
        "name": product_name(product)[:500],
        "description": Truncator(description).chars(5000, truncate="…"),
        "sku": str(product.dropi_id),
        "image": product_image_urls(product, request),
        "url": product_url,
        "brand": {"@type": "Brand", "name": product_brand(product)},
        "itemCondition": "https://schema.org/NewCondition",
        "offers": offer,
    }
    if getattr(product, "category", None):
        data["category"] = product.category.name
    # Solo con reseñas reales
    if getattr(product, "rating_count", 0) and product.rating_count > 0:
        data["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(round(product.rating_average, 1)),
            "reviewCount": str(product.rating_count),
            "bestRating": "5",
            "worstRating": "1",
        }
    crumbs = [("Inicio", "/")]
    if getattr(product, "category", None):
        crumbs.append((product.category.name, category_url(product.category)))
        if collection is not None and collection.category_id == product.category_id:
            crumbs.append((collection.name, collection.get_absolute_url()))
    crumbs.append((product_name(product), product.get_absolute_url()))
    return {"@context": "https://schema.org", "@graph": [data, breadcrumb_json_ld(request, crumbs)]}


def organization_json_ld(request) -> dict:
    """OnlineStore con los datos legales reales que estén configurados
    (razón social, RFC, dirección, contacto). Ningún campo se inventa: si
    falta en settings, no va."""
    from django.templatetags.static import static

    from .store_config import store_config

    cfg = store_config()
    base = absolute_url(request, "/")
    whatsapp = cfg["whatsapp"]
    org: dict = {
        "@type": "OnlineStore",
        "@id": base + "#store",
        "name": cfg["name"] or SITE_NAME,
        "url": base,
        "logo": absolute_url(request, static("images/logo.jpeg")),
        "areaServed": "MX",
        "currenciesAccepted": "MXN",
        "paymentAccepted": "Pago contra entrega",
        "hasMerchantReturnPolicy": RETURN_POLICY,
    }
    legal = cfg["legal_name"]
    if legal:
        org["legalName"] = legal
    nit = cfg["nit"]
    if nit:
        org["taxID"] = nit
    email = cfg["email"]
    if email:
        org["email"] = email
    address = {"@type": "PostalAddress", "addressCountry": "MX"}
    street = cfg["address"]
    if street:
        address["streetAddress"] = street
    city = cfg["city"]
    if city:
        address["addressLocality"] = city.split(",")[0].strip()
    org["address"] = address
    if whatsapp:
        org["contactPoint"] = {
            "@type": "ContactPoint",
            "contactType": "customer service",
            "telephone": f"+{whatsapp}",
            "availableLanguage": "es",
        }
    instagram = cfg["instagram"]
    if instagram:
        org["sameAs"] = [f"https://instagram.com/{instagram}"]
    return org
