from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from html import unescape

from catalog.models import Category


@dataclass(frozen=True)
class CategoryDefinition:
    key: str
    label: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class CategoryResult:
    category_key: str
    label: str
    confidence: int
    reason: str


STORE_CATEGORY_PREFIX = "store:"
MIN_CATEGORY_CONFIDENCE = 60

STORE_CATEGORIES: tuple[CategoryDefinition, ...] = (
    CategoryDefinition(
        "belleza",
        "Belleza",
        (
            "belleza", "maquillaje", "cosmetico", "cosmeticos", "brocha",
            "labial", "unas", "manicure", "manicura", "pedicure", "depilador", "facial",
            "skincare", "skin care", "cabello", "capilar", "rizador", "plancha pelo",
            "serum", "retinol", "acido hialuronico", "acne", "piel", "anti edad",
            "protector solar", "colageno", "kojic", "cortaunas", "esmalte",
            "depiladora", "afeitadora", "jabon", "salicilico", "vitamina",
            "hidratacion", "aclarante", "exfoliante", "crema", "anti estrias",
            "antiestrias", "antiestras", "anticelulitis", "minoxidil",
            "keratina", "shampoo", "pestanas",
            "cejas", "cepillo", "porcelana",
            "perfume", "perfumes", "fragancia", "parfum", "colonia", "eau de parfum",
            "eau de toilette", "amber oud", "orientica", "lattafa", "body splash",
            "autobronceador", "mascarilla", "crema dental", "crema dientes",
            "jabon facial", "jabon corporal", "niacinamida", "blanqueadora",
            "blanqueador dental", "dientes", "cepillo alisador", "cepillo plancha",
            "hot air brush", "plancha de pelo", "gluteos", "gorro de bano",
            "desodorante", "rollon",
        ),
    ),
    CategoryDefinition(
        "tecnologia",
        "Tecnología",
        (
            "tecnologia", "electronica", "gadget", "gadgets", "usb", "bluetooth",
            "audifonos", "parlante", "cargador", "smartwatch", "smart watch", "led", "camara",
            "celular", "telefono", "inalambrico", "airpods", "consola", "teclado",
            "mouse", "rgb", "adaptador", "convertidor", "microfono", "game stick",
            "gamer", "tipo c", "hdmi", "tripode", "estabilizador", "impresora",
            "antena", "tdt", "television", "digital", "wifi", "router", "modem",
            "repetidor", "control remoto", "drone", "proyector", "monitor",
            "bocina", "bocinas", "boombox", "booms box", "audifono",
            "tablet", "portatil", "power bank", "bateria externa", "memoria usb",
            "tarjeta memoria", "speaker", "auricular", "audifono", "audifonos",
            "luz led", "recargable", "reloj inteligente", "t500",
        ),
    ),
    CategoryDefinition(
        "hogar",
        "Hogar",
        (
            "hogar", "casa", "oficina", "ventilador", "abanico", "organizador",
            "limpieza", "aseo", "almohada", "sabana", "mueble", "lampara",
            "decoracion", "humidificador", "difusor", "aromaterapia", "closet",
            "armario", "ropero", "aspiradora", "tapete", "alfombra", "mesa", "silla",
            "navidad", "arbol navideno", "jardin",
            "repisa", "estante", "soporte pared", "mosquitero", "dispensador",
            "perchero", "zapatero", "organizador ropa", "canasta", "cesto",
            "colchon", "protector colchon", "toalla", "banera", "ducha",
            "cortina", "platero", "escoba", "trapero", "recogedor", "balde",
            "multiusos", "mopa", "ambientador",
            "bolsa almacenamiento", "almacenamiento al vacio", "aire acondicionado",
            "acondicionado",
        ),
    ),
    CategoryDefinition(
        "deporte_fitness",
        "Deporte y Fitness",
        (
            "deporte", "deportes", "fitness", "gym", "gimnasio", "ejercicio",
            "entrenamiento", "pesas", "mancuerna", "bandas elasticas", "yoga",
            "rodillera", "bicicleta", "balon", "pilates", "colchoneta",
            "rueda abdominal", "abdominales", "hand grip", "ejercitador",
            "theraband", "futbol", "ciclismo", "tobillera", "coderas",
            "guantes gym", "shaker", "natacion", "camping", "senderismo",
        ),
    ),
    CategoryDefinition(
        "salud_bienestar",
        "Salud y Bienestar",
        (
            "salud", "bienestar", "masaje", "masajeador", "ortopedico",
            # México
            "parche", "parches", "drenaje linfatico", "drenaje", "glp 1", "plantillas",
            "varices", "venas", "circulacion", "hongos", "metabolico", "metabolicos", "detox",
            "postura", "faja", "terapia", "dolor", "tens", "vaporizador",
            "nebulizador", "termometro", "presion arterial", "tensiometro",
            "oximetro", "glucometro", "fisioterapia", "corrector postura",
            "plantilla", "compresion", "cervical", "lumbar", "acupuntura",
            "almohadilla termica", "suplemento", "maca", "calostro",
            "antironquido", "antironquidos", "ronquido", "ronquidos",
            "protector bucal", "dormir", "respiracion", "ashwagandha",
            "turkesterona", "fenogreco", "vitamina", "omega", "magnesio",
            "copa menstrual", "calendula", "probiotico", "probiótico",
            "suplemento", "multivitaminico", "jarabe", "antireflujo",
            "antiacido", "clorofila", "clorofil", "desintoxicante",
            "colicos", "renal", "cartilago", "varices", "pastillero",
            "pastillas", "parche dolor", "parche gel", "gel enfriamiento", "cuello",
            "desintoxicantes", "almohadillas desintoxicantes", "almohadillas pies",
            "gel enfriamient", "parche gel enfriamient", "gel de enfriamient",
            "parche de gel",
        ),
    ),
    CategoryDefinition(
        "cocina",
        "Cocina",
        (
            "cocina", "olla", "sarten", "freidora", "licuadora", "batidora",
            "termo", "vaso", "cubiertos", "cuchillo", "reposteria", "alimentos",
            "utensilio", "utensilios", "air fryer", "porta platos", "escurridor",
            "exprimidor", "procesador", "picatodo", "molde", "espatula",
            "tabla picar", "botella", "taza", "jarra", "organizador cocina",
            "selladora", "gramera", "bascula cocina", "horno", "parrilla",
            "sanduchera", "wafflera", "cafetera", "termo digital",
            "termo inteligente", "tupper", "lonchera", "pelador", "rallador",
            "colador", "hielera", "sellado al vacio", "sellar al vacio",
            "empacador", "bolsa termica", "ablandador carne", "ablandador carnes",
            "abrelatas",
        ),
    ),
    CategoryDefinition(
        "vehiculos",
        "Vehículos",
        (
            "vehiculo", "vehiculos", "carro", "moto", "automotriz", "llanta",
            "retrovisor", "soporte celular carro", "limpiaparabrisas", "auto",
            "coche", "faros", "soporte celular auto",
            "automovil", "ambientador carro", "aspiradora carro",
            "motocicleta", "rin", "parabrisas", "cargador carro", "pulidora",
            "cera", "desengrasante", "brilladora", "renovador", "antiempanante",
            "alarma moto", "casco", "luces carro", "camara reversa", "compresor aire",
            "inflallanta", "porta celular carro", "forro carro", "tapete carro",
        ),
    ),
    CategoryDefinition(
        "moda_accesorios",
        "Moda y Accesorios",
        (
            "moda", "accesorio", "accesorios", "bolso", "reloj", "collar",
            "pulsera", "aretes", "bisuteria", "ropa", "textil", "tenis",
            "sandalia", "gafas", "anillo", "joya", "joyeria", "cadena", "dije",
            "camiseta", "pantalon", "chaqueta", "vestido", "zapatos", "maleta",
            "billetera", "morral", "lentes", "gorra", "sombrero", "cinturon",
            "bufanda", "guantes", "accesorio moda", "canguro", "riñonera",
            "rinonera", "monedero", "porta celular", "strap", "scrunchie",
            "balaca", "polo", "t shirt", "tshirt", "boxer", "boxers",
            "media", "medias", "panty", "pantys", "cachetero", "brasier",
            "cacheteros", "camisilla", "camisillas", "blusa", "short", "jean",
            "jogger", "leggins", "interior", "hilo",
            "encaje", "cinturilla", "tatuaje temporal", "tatuajes temporales",
            "fajon", "relojjoefox", "joefox", "doblehora", "ana dig", "ana-dig",
            "nike", "adidas", "caterpillar", "jordan", "calzado", "bota",
            "botas", "baleta", "botines", "mocasines", "caballero", "dama",
            "puntera", "unisex",
        ),
    ),
    CategoryDefinition(
        "bebes",
        "Bebés",
        (
            "bebe", "bebes", "baby", "infantil", "nino", "nina", "ninos", "ninas",
            "pañal", "panal", "panales", "tetero", "biberon", "chupo", "coche bebe",
            "cuna", "corral bebe", "cambiador", "porta bebe", "portabebe",
            "extractor leche", "extractor de leche", "sacaleches", "lactancia", "materna", "esterilizador biberon",
            "babero", "caminador bebe", "silla comedor bebe", "orinal infantil",
            "andador", "andadera", "primeros pasos",
        ),
    ),
    CategoryDefinition(
        "mascotas",
        "Mascotas",
        (
            "mascota", "mascotas", "perro", "gato", "perros", "gatos",
            "collar mascota", "comedero", "bebedero", "arnes", "correa",
            "cama mascota", "guacal", "cepillo mascota", "pelaje",
            "juguete mascota", "arena gato", "rascador", "bozal",
            "cortaunas mascota", "dispensador comida", "doggy", "bandeja doggy",
            "arenero", "recogedor mascota", "comedero mascota", "bebedero mascota",
            "pechera perro", "pechera gato", "cepillo para mascota",
        ),
    ),
    CategoryDefinition(
        "herramientas",
        "Herramientas",
        (
            "herramienta", "herramientas", "taladro", "destornillador",
            "soldador", "llave", "llaves", "multimetro", "cortador", "alicate", "broca",
            "brocas", "rache", "atornillador", "guadana", "guadanadora",
            "guadanadora", "cuchilla guadana", "pinza", "copa", "martillo",
            "cautin", "pulidora", "sierra", "nivel laser", "metro",
            "cinta metrica", "caja herramientas", "tornillo", "grapa", "engrapadora",
            "aguja", "agujas", "coser", "costura", "arandela", "arandelas",
            "tijera podar", "podadora", "hidrolavadora", "manguera", "silicona",
            "pistola silicona", "remachadora", "prensa", "cizalla",
            "carbon", "carbones", "lijadora", "ruteadora", "sopladora",
            "estibador", "rodillo", "rodillos", "mezclador electrico",
            "pistola electrica", "compresor", "juego de herramientas",
            "llave inglesa", "repuesto", "tornillos", "pistola de tornillos",
            "adaptador de pistola", "adaptador de sierra", "adaptador de taladro",
            "motosierra", "esmeril",
        ),
    ),
    CategoryDefinition(
        "fiesta_pinateria",
        "Fiesta y Piñatería",
        (
            "fiesta", "pinateria", "piñateria", "halloween", "disfraz",
            "cumpleanos", "cumpleaños", "plato", "platos", "plato carton",
            "vaso fiesta", "vasos fiesta", "globo", "globos", "globo metalizado",
            "bolsa regalo", "bolsa de regalo", "serpentina", "confeti", "antifaz",
            "alas de hada", "alas angel", "decoracion halloween", "bouquet globos",
            "borde dorado", "puntos blancos", "metalizado", "tornasol",
            "alas", "angel", "alas angel negro",
        ),
    ),
    CategoryDefinition(
        "papeleria",
        "Papelería",
        (
            "papeleria", "libro", "libros", "cuaderno", "agenda", "cartuchera",
            "caligrafia", "montessori", "marcador", "marcadores", "lapiz",
            "lapices", "papel sticker", "rollo colorear", "colorear",
            "dibujo", "pines", "rollo adhesivos", "mini impresora", "impresion",
            "papel", "plumones", "doble punta", "abaco", "educativo", "matematica",
        ),
    ),
    CategoryDefinition(
        "seguridad",
        "Seguridad",
        (
            "seguridad", "defensa personal", "taser", "gas pimienta", "pimienta",
            "alarma", "sirena", "candado", "camara seguridad", "sensor movimiento",
            "sensor puerta", "cerradura", "cerradura inteligente", "linterna tactica",
            "baston defensa", "baston tactico", "kit emergencia", "botiquin",
        ),
    ),
    CategoryDefinition(
        "bienestar_intimo",
        "Bienestar Íntimo",
        (
            "sex shop", "lubricantes", "lubricante intimo", "lubricante íntimo",
            "gel anal", "gel intimo", "gel íntimo", "dildo", "dildos",
            "erotico", "erotica", "erótico", "erótica", "retardante",
            "estrechante", "aceite lubricante comestible", "comestible con sabor",
            "cosmetologia erotica", "cosmetología erótica",
        ),
    ),
    CategoryDefinition(
        "juguetes",
        "Juguetes",
        (
            "juguete", "juguetes", "didactico", "rompecabezas", "lego", "bloques",
            "lancha rc", "carro rc", "auto rc", "lapicera 3d", "pluma 3d",
            "muneca", "carro juguete", "dinosaurio", "alcancia", "peluche",
            "cubo rubik", "juego mesa", "juego de mesa", "juegos", "cartas", "patineta infantil",
            "ajedrez", "jugueteria", "juguetería", "hidrogel", "pistola hidrogel",
            "pistola de hidrogel", "bolas de gel", "pelotas", "burbujas",
            "burbujero", "pistola burbujas", "avion infantil", "bateria infantil",
            "labubu", "plastilina", "cometa",
        ),
    ),
    CategoryDefinition("otros", "Otros", ()),
)

_CATEGORY_BY_KEY = {category.key: category for category in STORE_CATEGORIES}

_WEAK_KEYWORDS = {
    "belleza": {"cabello", "facial", "piel", "colageno", "cepillo", "jabon", "crema", "vitamina"},
    "tecnologia": {"tecnologia", "electronica", "led", "celular", "telefono", "usb", "inalambrico", "recargable"},
    "hogar": {"casa", "oficina", "decoracion", "mesa", "silla", "organizador", "dispensador", "ambientador"},
    "salud_bienestar": {"salud", "bienestar", "dolor", "tens", "parche", "parches"},
    "cocina": {"vaso", "termo", "alimentos", "botella", "taza", "jarra", "lonchera"},
    "vehiculos": {"moto", "carro", "vehiculo", "vehiculos"},
    "moda_accesorios": {"accesorio", "accesorios", "moda", "ropa", "bisuteria"},
    "bebes": {"infantil", "nino", "nina", "ninos", "ninas", "baby"},
    "mascotas": {"mascota", "mascotas", "perro", "gato"},
    "herramientas": {"herramienta", "herramientas", "llave", "cortador", "copa", "silicona"},
    "fiesta_pinateria": {"fiesta", "plato", "platos", "globo", "globos", "metalizado", "antifaz"},
    "papeleria": {"pines"},
    "seguridad": {"alarma", "pimienta", "candado", "botiquin"},
    "bienestar_intimo": {"lubricantes"},
    "juguetes": {"nino", "nina", "bebe", "bebes"},
}


def normalize_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(value or ""))
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=\d)", " ", text)
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def contains_term(text: str, term: str) -> bool:
    normalized = normalize_text(term)
    if not normalized:
        return False
    return contains_normalized_term(text, normalized)


def contains_normalized_term(text: str, normalized_term: str) -> bool:
    return f" {normalized_term} " in f" {text} "


@lru_cache(maxsize=1)
def category_keyword_rules() -> dict[str, tuple[tuple[str, str, bool], ...]]:
    rules: dict[str, tuple[tuple[str, str, bool], ...]] = {}
    for definition in STORE_CATEGORIES:
        weak_keywords = {normalize_text(keyword) for keyword in _WEAK_KEYWORDS.get(definition.key, set())}
        rules[definition.key] = tuple(
            (keyword, normalize_text(keyword), normalize_text(keyword) in weak_keywords)
            for keyword in definition.keywords
        )
    return rules


def store_category_dropi_id(key: str) -> str:
    return f"{STORE_CATEGORY_PREFIX}{key}"


def ensure_store_category(key: str) -> Category:
    definition = _CATEGORY_BY_KEY.get(key, _CATEGORY_BY_KEY["otros"])
    category, _created = Category.objects.get_or_create(
        dropi_id=store_category_dropi_id(definition.key),
        defaults={"name": definition.label},
    )
    if category.name != definition.label or category.parent_id is not None:
        category.name = definition.label
        category.parent = None
        category.save(update_fields=["name", "parent"])
    return category


def ensure_store_categories() -> list[Category]:
    return [ensure_store_category(category.key) for category in STORE_CATEGORIES]


# Categorías de Dropi México → tienda. Solo se usan cuando las palabras clave
# no deciden (resultado "otros"): en Dropi México vienen bien asignadas, y sin
# esto ~16% del catálogo caía en "Otros" (muestra de 240, 2026-11-04).
DROPI_MX_CATEGORY_FALLBACK = {
    "hogar": "hogar", "natural home": "hogar", "aseo": "hogar",
    "cocina": "cocina",
    "mascotas": "mascotas",
    "moda": "moda_accesorios", "calzado": "moda_accesorios",
    "tecnologia": "tecnologia", "gadgets": "tecnologia",
    "belleza": "belleza",
    "salud": "salud_bienestar", "bienestar": "salud_bienestar", "cuidado personal": "salud_bienestar",
    "deportes": "deporte_fitness", "camping": "deporte_fitness", "pesca": "deporte_fitness",
    "bebe": "bebes",
    "sex shop": "bienestar_intimo",
    "vehiculos": "vehiculos",
    "defensa personal": "seguridad",
    "jugueteria": "juguetes",
    "herramientas": "herramientas",
}


def classify_product_text(
    *,
    name: str,
    description: str = "",
    dropi_category_name: str = "",
) -> CategoryResult:
    result = _classify_by_keywords(name=name, description=description, dropi_category_name=dropi_category_name)
    if result.category_key != "otros":
        return result
    key = DROPI_MX_CATEGORY_FALLBACK.get(normalize_text(dropi_category_name))
    if not key:
        # Varias categorías de Dropi juntas ("Salud Bienestar"): la primera que se conozca.
        normalized = normalize_text(dropi_category_name)
        key = next((v for k, v in DROPI_MX_CATEGORY_FALLBACK.items() if contains_normalized_term(normalized, k)), None)
    if not key:
        return result
    definition = _CATEGORY_BY_KEY[key]
    return CategoryResult(definition.key, definition.label, 50, f"categoría de Dropi: {dropi_category_name}")


def _classify_by_keywords(
    *,
    name: str,
    description: str = "",
    dropi_category_name: str = "",
) -> CategoryResult:
    normalized_name = normalize_text(name)
    normalized_description = normalize_text(description)
    normalized_dropi = normalize_text(dropi_category_name)
    searchable = {
        "name": normalized_name,
        "description": normalized_description,
        "dropi": normalized_dropi,
    }
    combined_text = " ".join(searchable.values())

    scores: dict[str, int] = {}
    reasons: dict[str, list[str]] = {}
    for definition in STORE_CATEGORIES:
        if definition.key == "otros":
            continue
        score = 0
        matched: list[str] = []
        for keyword, normalized_keyword, weak in category_keyword_rules()[definition.key]:
            if not contains_normalized_term(combined_text, normalized_keyword):
                continue
            if contains_normalized_term(searchable["name"], normalized_keyword):
                score += 2 if weak else 6
                matched.append(keyword)
            if contains_normalized_term(searchable["description"], normalized_keyword):
                score += 1 if weak else 3
                matched.append(keyword)
            if contains_normalized_term(searchable["dropi"], normalized_keyword):
                score += 0 if weak else 6
                matched.append(keyword)
        if score:
            scores[definition.key] = score
            reasons[definition.key] = matched

    if not scores:
        return CategoryResult("otros", _CATEGORY_BY_KEY["otros"].label, 10, "fallback: sin coincidencias")

    best_key, best_score = max(scores.items(), key=lambda item: item[1])
    definition = _CATEGORY_BY_KEY[best_key]
    confidence = min(95, max(45, best_score * 10))
    unique_matches = list(dict.fromkeys(reasons[best_key]))[:4]
    reason = "match: " + ", ".join(unique_matches)
    if confidence < MIN_CATEGORY_CONFIDENCE:
        return CategoryResult(
            "otros",
            _CATEGORY_BY_KEY["otros"].label,
            confidence,
            f"low confidence: {definition.label} ({reason})",
        )
    return CategoryResult(definition.key, definition.label, confidence, reason)
