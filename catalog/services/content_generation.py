"""
Generación de contenido único (meta_title, meta_description,
description_unique) por PLANTILLAS + slot-filling determinista — sin IA,
sin llamadas a servicios externos.

Cómo evita ser 100% idéntico entre productos parecidos:
  - La combinación de apertura/beneficio/cierre para cada producto se elige
    con una función determinista sobre Product.pk (hash multiplicativo de
    Knuth), no al azar en cada corrida — mismo producto siempre da el mismo
    texto (idempotente), pero productos distintos casi nunca caen en la
    misma combinación exacta de las 3 franjas.
  - Los beneficios están agrupados por categoría (18 categorías curadas de
    la tienda: ~20-22 frases por franja), no son genéricos puros.
  - Cuando la descripción cruda de Dropi tiene una oración real
    aprovechable, se inyecta como "ancla" de contenido concreto del
    producto — y el meta_description la prioriza sobre el beneficio
    genérico cuando existe, porque es el campo que Google muestra en
    resultados de búsqueda.

Límite honesto: con bancos finitos y miles de productos, SIEMPRE habrá
alguna repetición en la parte "de relleno" (no es solucionable al 100% sin
IA). Ampliar los bancos reduce la frecuencia de colisión, no la elimina.
"""
from __future__ import annotations

import re
from html import unescape

from django.utils.text import Truncator

_TAG_RE = re.compile(r"<[^>]+>")
_HTML_BLOCK_RE = re.compile(r"</?(?:p|div|li|ul|ol|br|h[1-6]|section|article|blockquote)[^>]*>", re.I)
_WS_RE = re.compile(r"\s+")
_BULLET_RE = re.compile(r"^[\-\*•\s]+")

# Suppliers commonly append a full warranty/returns-policy section AFTER the
# real feature content, often as numbered clauses ("1. Alcance:", "7.
# Resolución:", "9. Limitación de Responsabilidad:"). That section is all
# well-formed, longish sentences — exactly what "pick the longest candidate"
# favors — so keyword-blocking alone is whack-a-mole (found via a real
# product whose description had ~10 different warranty-condition sentences,
# each needing its own blocklist entry). Cutting the text at the first line
# that looks like the start of that section is far more robust: everything
# after it is simply never considered as anchor material.
_WARRANTY_SECTION_RE = re.compile(
    r"pol[ií]tica\s+de\s+garant|garant[ií]as?\s+se\s+aplica|^\s*\d+\.\s",
    re.IGNORECASE,
)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "]+",
    flags=re.UNICODE,
)
_LETTERS_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}")

MIN_ANCHOR_CHARS = 25
MAX_ANCHOR_CHARS = 220

# Boilerplate that should never be quoted as a product "characteristic" —
# warranty exclusions, return policy, legal/contact text. These sentences
# are often long and grammatically well-formed (unlike bullet fragments),
# so without this filter they win the "pick the longest candidate"
# selection over genuine feature text. Found via a real example: a
# warranty-void clause ("Mal uso del producto: golpes, caídas...") got
# picked as the anchor for a smartwatch.
_ANCHOR_EXCLUDE_RE = re.compile(
    r"\b("
    r"garant[ií]a|garantia|devoluci[oó]n|devolucion|reembolso|"
    r"mal\s+uso|manual\s+de\s+usuario|manual\s+del\s+usuario|"
    r"t[eé]rminos\s+y\s+condiciones|terminos\s+y\s+condiciones|"
    r"pol[ií]tica\s+de|politica\s+de|responsabilidad|"
    r"no\s+cubre|no\s+aplica|da[ñn]os?\s+caus|sobrecarga|"
    r"empaque\s+original|defectos?\s+de\s+f[aá]brica|defectos?\s+de\s+fabrica"
    r")\b",
    re.IGNORECASE,
)

# Knuth's multiplicative hashing constant (2^32 * golden ratio) — deterministic
# spread of small sequential integers (Product.pk) across a bank's indices,
# without relying on Python's str hash() (randomized per-process by default).
_HASH_MULT = 2654435761


def _pick(bank: list[str], pk: int, salt: int) -> str:
    idx = (pk * _HASH_MULT + salt) % len(bank)
    return bank[idx]


def _clean_text(raw: str) -> str:
    text = unescape(_TAG_RE.sub(" ", raw or ""))
    text = _WS_RE.sub(" ", text).strip()
    return text


def _clean_name(raw: str) -> str:
    text = _EMOJI_RE.sub("", raw or "")
    text = _WS_RE.sub(" ", text).strip()
    return text.title() if text else "Este producto"


def has_usable_name(name: str) -> bool:
    """False para nombres basura (vacíos, solo puntuación/dígitos, tipo
    '..' o '---'). Candidato a excluir de la generación de contenido — y en
    general, de limpieza de catálogo aparte de esto."""
    cleaned = _EMOJI_RE.sub("", name or "")
    return bool(_LETTERS_RE.search(cleaned))


def extract_anchor_sentence(raw_description: str) -> str:
    """Una oración/fragmento real de la descripción cruda de Dropi para
    anclar el texto en algo concreto del producto. Devuelve "" cuando no hay
    ninguna oración utilizable (descripción vacía, puro spam ya limpiado por
    sanitize_product_description en el import, solo fragmentos tipo bullet
    sin contenido real, o una descripción que es 100% sección de garantía)
    — en ese caso el resto del generador sigue funcionando igual, sin ancla,
    usando solo nombre/categoría/precio/atributos.

    Preserva límites de párrafo (a diferencia de _clean_text) para poder
    cortar la descripción justo donde empieza una sección de garantía/
    política de devoluciones, en vez de solo bloquear palabras clave — ver
    _WARRANTY_SECTION_RE."""
    raw = raw_description or ""
    text = unescape(_HTML_BLOCK_RE.sub("\n", raw))
    text = _TAG_RE.sub(" ", text)
    lines = [_WS_RE.sub(" ", ln).strip() for ln in text.split("\n")]

    kept_lines = []
    for ln in lines:
        if not ln:
            continue
        if _WARRANTY_SECTION_RE.search(ln):
            break
        kept_lines.append(ln)

    text = " ".join(kept_lines)
    if not text:
        return ""
    chunks = re.split(r"[.!?]+", text)
    candidates = []
    for chunk in chunks:
        chunk = _BULLET_RE.sub("", chunk).strip(" -•\t:")
        if not chunk:
            continue
        word_count = len(chunk.split())
        if not (MIN_ANCHOR_CHARS <= len(chunk) <= MAX_ANCHOR_CHARS and word_count >= 5):
            continue
        if _ANCHOR_EXCLUDE_RE.search(chunk):
            continue
        candidates.append(chunk)
    if not candidates:
        return ""
    candidates.sort(key=len, reverse=True)
    best = candidates[0]
    if not best.endswith((".", "!", "?")):
        best += "."
    return best[0].upper() + best[1:]


def _attribute_clause(product) -> str:
    if not product.variants:
        return ""
    labels = set()
    for v in product.variants:
        if not isinstance(v, dict):
            continue
        for attr in v.get("attribute_values") or []:
            if isinstance(attr, dict) and attr.get("value"):
                labels.add(str(attr["value"]))
    if len(labels) >= 2:
        return "Disponible en varias opciones para que elijas la que más te guste."
    return ""


OPENERS: list[str] = [
    "{name} es una excelente opción dentro de {category}.",
    "Si buscas productos de {category}, {name} es una alternativa a considerar.",
    "{name} forma parte de nuestra selección de {category} en Pegasus Store.",
    "Dentro de {category}, {name} destaca por su relación calidad-precio.",
    "{name} es uno de los productos más buscados en {category}.",
    "Si estás explorando {category}, {name} vale la pena revisarlo.",
    "{name} llegó a Pegasus Store dentro de nuestra sección de {category}.",
    "¿Buscando algo confiable en {category}? {name} es una gran opción.",
    "{name} combina practicidad y buen precio, ideal dentro de {category}.",
    "En nuestra sección de {category}, {name} es de los favoritos.",
    "{name} es una alternativa sólida si estás mirando {category}.",
    "Entre lo más pedido en {category} está {name}.",
    "{name} está disponible ahora en nuestra sección de {category}.",
    "Si {category} es lo tuyo, {name} no debería faltarte.",
    "{name} suma buena relación calidad-precio dentro de {category}.",
    "Pensando en {category}, {name} es una opción a tener en cuenta.",
    "{name} es de los productos con mejor acogida en {category}.",
    "Dale un vistazo a {name}, parte de nuestra selección de {category}.",
    "{name} está pensado para quienes buscan algo confiable en {category}.",
    "En Pegasus Store, {name} es de lo más consultado en {category}.",
    "{name} se suma a nuestro catálogo de {category} con buena acogida.",
    "Si estás comparando opciones en {category}, {name} vale la pena mirarlo.",
]

GENERIC_BENEFITS: list[str] = [
    "Un producto pensado para el uso diario, sin complicaciones.",
    "Fácil de usar desde el primer día.",
    "Buena relación calidad-precio dentro de su categoría.",
    "Práctico para el día a día en casa o en la calle.",
    "Ideal si buscas algo funcional sin gastar de más.",
    "Pensado para resolver una necesidad concreta, sin vueltas.",
    "Un producto versátil que se adapta a distintos usos.",
    "Fácil de guardar y de llevar a donde lo necesites.",
    "Pensado para quienes buscan algo práctico y accesible.",
    "Una opción sencilla para cubrir una necesidad puntual.",
    "Cumple lo básico sin complicarte con instrucciones largas.",
    "Un producto pensado para durar en el uso diario.",
    "Práctico, sencillo y fácil de incorporar a tu rutina.",
    "Pensado para quienes buscan algo directo, sin vueltas.",
    "Una alternativa práctica frente a opciones más costosas.",
    "Listo para usar apenas lo recibes, sin armar complicado.",
    "Un producto pensado para resolver, no para complicarte.",
    "Fácil de usar, sin curva de aprendizaje larga.",
    "Pensado para el uso cotidiano, en casa o fuera.",
    "Una opción práctica para tener a la mano cuando la necesites.",
]

CATEGORY_BENEFITS: dict[str, list[str]] = {
    "Belleza": [
        "Pensado para sumarse a tu rutina de cuidado personal sin complicarte.",
        "Ideal para quienes buscan verse y sentirse bien todos los días.",
        "Fácil de incorporar a tu rutina diaria de belleza.",
        "Una opción práctica para tu cuidado personal.",
        "Pensado para dejar tu piel o cabello con mejor apariencia.",
        "Ideal para tu rutina de skincare, sin complicarte con pasos largos.",
        "Un aliado más en tu rutina de belleza diaria.",
        "Fácil de aplicar, pensado para el uso frecuente.",
        "Pensado para realzar tu cuidado personal sin gastar de más.",
        "Ideal si buscas renovar tu rutina de belleza.",
        "Práctico para tener siempre a la mano en el baño o el tocador.",
        "Pensado para verte bien sin invertir demasiado tiempo.",
        "Una opción accesible para cuidar tu piel, cabello o uñas.",
        "Ideal para regalar a quien disfruta cuidarse.",
        "Fácil de sumar a tu rutina de belleza, sin pasos complicados.",
        "Pensado para el cuidado diario, en casa o de viaje.",
        "Una alternativa práctica frente a tratamientos más costosos.",
        "Ideal para quienes cuidan su imagen sin complicarse.",
        "Pensado para acompañarte en tu rutina de belleza día a día.",
        "Fácil de llevar contigo, ideal también para viajar.",
    ],
    "Tecnología": [
        "Funcionalidad práctica para el día a día, sin vueltas.",
        "Pensado para quienes buscan tecnología útil a buen precio.",
        "Fácil de configurar y usar desde el primer momento.",
        "Una opción práctica si buscas renovar tus gadgets.",
        "Ideal para quienes disfrutan de la tecnología sin gastar de más.",
        "Pensado para el uso diario, en casa, la oficina o la calle.",
        "Una alternativa accesible frente a otras marcas más costosas.",
        "Fácil de usar, sin necesidad de ser un experto en tecnología.",
        "Ideal para tener siempre a la mano tu conectividad.",
        "Pensado para acompañarte en tu rutina digital diaria.",
        "Una opción práctica para regalar a quien le gusta la tecnología.",
        "Fácil de llevar contigo a donde vayas.",
        "Ideal si buscas algo funcional para tu día a día tecnológico.",
        "Pensado para resolver una necesidad concreta con tecnología accesible.",
        "Una alternativa práctica para renovar lo que ya tienes.",
        "Fácil de instalar y de empezar a usar de inmediato.",
        "Ideal para quienes buscan buena relación calidad-precio en tecnología.",
        "Pensado para el hogar, la oficina o el uso personal.",
        "Una opción práctica para sumar a tu colección de gadgets.",
        "Fácil de configurar, pensado para cualquier nivel de experiencia.",
    ],
    "Hogar": [
        "Pensado para hacerte la vida más fácil en casa.",
        "Súmalo a tu hogar sin complicarte con instalaciones difíciles.",
        "Ideal para mantener tu casa más cómoda y organizada.",
        "Una opción práctica para el día a día del hogar.",
        "Pensado para resolver una necesidad concreta en casa.",
        "Ideal para quienes buscan orden y comodidad sin gastar de más.",
        "Fácil de ubicar en cualquier espacio de tu casa.",
        "Una alternativa práctica frente a soluciones más costosas.",
        "Pensado para el hogar, sin necesitar herramientas especiales.",
        "Ideal para regalar a quien está armando o renovando su casa.",
        "Fácil de limpiar y de mantener en buen estado.",
        "Una opción práctica para tener siempre a la mano en casa.",
        "Pensado para hacer más cómodo tu día a día doméstico.",
        "Ideal si buscas algo funcional para tu hogar.",
        "Fácil de instalar, sin complicarte con manuales largos.",
        "Una alternativa accesible para renovar espacios de tu casa.",
        "Pensado para el uso diario en cualquier rincón del hogar.",
        "Ideal para quienes buscan practicidad en las tareas de casa.",
        "Una opción práctica para organizar mejor tu espacio.",
        "Fácil de usar desde el primer día en tu hogar.",
    ],
    "Deporte y Fitness": [
        "Pensado para acompañarte en tu rutina de entrenamiento.",
        "Ideal para quienes buscan mantenerse activos sin gastar de más.",
        "Fácil de llevar contigo a donde entrenes.",
        "Una opción práctica para sumar a tu rutina deportiva.",
        "Pensado para el gimnasio, el parque o tu casa.",
        "Ideal si estás empezando a entrenar y buscas algo accesible.",
        "Fácil de guardar y de llevar a donde vayas a entrenar.",
        "Una alternativa práctica frente a equipos más costosos.",
        "Pensado para quienes buscan constancia en su rutina física.",
        "Ideal para complementar tus entrenamientos en casa.",
        "Fácil de usar, sin necesitar experiencia previa.",
        "Una opción práctica para tu rutina de ejercicio diaria.",
        "Pensado para acompañarte tanto en cardio como en fuerza.",
        "Ideal para quienes buscan resultados sin complicarse con equipos grandes.",
        "Fácil de incorporar a tu rutina, sin importar tu nivel.",
        "Una alternativa accesible para entrenar en casa o al aire libre.",
        "Pensado para el día a día de quienes se mantienen activos.",
        "Ideal para regalar a quien disfruta el deporte.",
        "Fácil de transportar, pensado para entrenar donde sea.",
        "Una opción práctica si buscas mantenerte en movimiento.",
    ],
    "Salud y Bienestar": [
        "Pensado para acompañar tu bienestar en el día a día.",
        "Ideal si buscas cuidar de tu salud sin complicaciones.",
        "Una opción práctica para sumar a tu rutina de bienestar.",
        "Fácil de incorporar a tu día a día.",
        "Pensado para el cuidado personal desde casa.",
        "Ideal para quienes buscan sentirse mejor sin complicarse.",
        "Una alternativa práctica para tu bienestar diario.",
        "Fácil de usar, sin necesitar indicaciones complicadas.",
        "Pensado para acompañarte en tu rutina de autocuidado.",
        "Ideal para tener siempre a la mano en casa.",
        "Una opción práctica si buscas cuidar tu bienestar general.",
        "Fácil de llevar contigo si lo necesitas fuera de casa.",
        "Pensado para sumar comodidad a tu rutina diaria de salud.",
        "Ideal para regalar a quien se preocupa por su bienestar.",
        "Una alternativa accesible frente a opciones más costosas.",
        "Fácil de incorporar a tu rutina, sin cambios drásticos.",
        "Pensado para acompañarte en el cuidado de tu bienestar físico.",
        "Ideal si buscas algo práctico para tu día a día.",
        "Una opción sencilla para sumar a tu cuidado personal.",
        "Fácil de usar desde el primer momento.",
    ],
    "Cocina": [
        "Pensado para facilitarte el día a día en la cocina.",
        "Ideal para quienes disfrutan cocinar sin complicarse.",
        "Una opción práctica para tener siempre a la mano en casa.",
        "Fácil de usar y de limpiar después de cocinar.",
        "Pensado para ahorrarte tiempo en la cocina.",
        "Ideal si buscas algo funcional para el día a día culinario.",
        "Una alternativa práctica frente a utensilios más costosos.",
        "Fácil de guardar, sin ocupar mucho espacio en la cocina.",
        "Pensado para quienes cocinan todos los días en casa.",
        "Ideal para regalar a quien disfruta cocinar.",
        "Una opción práctica para preparar comidas más rápido.",
        "Fácil de usar, incluso si no eres experto en la cocina.",
        "Pensado para sumar practicidad a tus recetas de siempre.",
        "Ideal si buscas renovar tus utensilios de cocina.",
        "Una alternativa accesible para equipar mejor tu cocina.",
        "Fácil de limpiar, pensado para el uso frecuente.",
        "Pensado para el día a día de quienes cocinan en casa.",
        "Ideal para quienes buscan practicidad al preparar sus comidas.",
        "Una opción práctica para tu cocina, sin gastar de más.",
        "Fácil de usar desde la primera vez que lo pruebes.",
    ],
    "Vehículos": [
        "Pensado para el cuidado diario de tu vehículo.",
        "Ideal para tener siempre a la mano en el carro o la moto.",
        "Una opción práctica para el mantenimiento de tu vehículo.",
        "Fácil de usar sin necesitar herramientas extra.",
        "Pensado para quienes cuidan su carro o moto en casa.",
        "Ideal si buscas mantener tu vehículo en buen estado.",
        "Una alternativa práctica frente a servicios más costosos.",
        "Fácil de guardar en la guantera o el baúl.",
        "Pensado para el uso frecuente, dentro o fuera del vehículo.",
        "Ideal para regalar a quien disfruta cuidar su carro.",
        "Una opción práctica para tener a la mano en cada viaje.",
        "Fácil de instalar, sin necesitar un mecánico.",
        "Pensado para sumar comodidad a tus trayectos diarios.",
        "Ideal si buscas algo funcional para tu vehículo.",
        "Una alternativa accesible para el mantenimiento básico.",
        "Fácil de usar, pensado para conductores de cualquier nivel.",
        "Pensado para el cuidado exterior o interior de tu vehículo.",
        "Ideal para quienes buscan practicidad al mantener su carro o moto.",
        "Una opción práctica para sumar a tu kit de vehículo.",
        "Fácil de llevar contigo en cada trayecto.",
    ],
    "Moda y Accesorios": [
        "Pensado para sumar a tu estilo sin gastar de más.",
        "Ideal para combinar con lo que ya tienes en el clóset.",
        "Una opción práctica para renovar tu look.",
        "Fácil de combinar con distintos outfits.",
        "Pensado para quienes buscan renovar su estilo sin complicarse.",
        "Ideal para regalar a quien disfruta la moda.",
        "Una alternativa accesible frente a marcas más costosas.",
        "Fácil de llevar en el día a día o para ocasiones especiales.",
        "Pensado para sumar un accesorio versátil a tu clóset.",
        "Ideal si buscas algo que combine con varios estilos.",
        "Una opción práctica para completar tu outfit.",
        "Fácil de combinar, ideal para el día a día.",
        "Pensado para quienes buscan verse bien sin complicarse.",
        "Ideal para renovar tu guardarropa sin gastar de más.",
        "Una alternativa práctica para sumar variedad a tu estilo.",
        "Fácil de llevar contigo a donde vayas.",
        "Pensado para complementar looks casuales o formales.",
        "Ideal para regalar en cualquier ocasión especial.",
        "Una opción práctica si buscas renovar tus accesorios.",
        "Fácil de combinar con tu estilo personal.",
    ],
    "Bebés": [
        "Pensado para el día a día con tu bebé.",
        "Ideal para acompañarte en la crianza sin complicaciones.",
        "Una opción práctica para el cuidado diario del bebé.",
        "Fácil de usar y de llevar a donde vayas con tu bebé.",
        "Pensado para facilitarte la rutina diaria con el bebé.",
        "Ideal para regalar en un baby shower o nacimiento.",
        "Una alternativa práctica frente a productos más costosos.",
        "Fácil de limpiar, pensado para el uso frecuente.",
        "Pensado para el bienestar y la comodidad del bebé.",
        "Ideal si buscas algo funcional para el cuidado diario.",
        "Una opción práctica para tener siempre a la mano en casa.",
        "Fácil de transportar cuando sales con tu bebé.",
        "Pensado para acompañarte en cada etapa de la crianza.",
        "Ideal para regalar a familiares o amigos que esperan bebé.",
        "Una alternativa accesible para equipar la habitación del bebé.",
        "Fácil de usar, incluso para primerizos.",
        "Pensado para sumar comodidad a la rutina diaria con el bebé.",
        "Ideal si buscas practicidad en el día a día con niños pequeños.",
        "Una opción práctica para el cuidado y la seguridad del bebé.",
        "Fácil de guardar y de tener siempre listo para usar.",
    ],
    "Mascotas": [
        "Pensado para el bienestar diario de tu mascota.",
        "Ideal para consentir a tu peludo sin gastar de más.",
        "Una opción práctica para el cuidado de tu mascota.",
        "Fácil de usar en el día a día con tu mascota.",
        "Pensado para facilitarte el cuidado diario de perros o gatos.",
        "Ideal para regalar a quien tiene una mascota en casa.",
        "Una alternativa práctica frente a productos más costosos.",
        "Fácil de limpiar, pensado para el uso frecuente.",
        "Pensado para el bienestar y la comodidad de tu mascota.",
        "Ideal si buscas algo funcional para el cuidado de tu peludo.",
        "Una opción práctica para tener siempre a la mano en casa.",
        "Fácil de transportar cuando sales con tu mascota.",
        "Pensado para acompañarte en el cuidado diario de tu mascota.",
        "Ideal para sumar comodidad a la rutina de tu peludo.",
        "Una alternativa accesible para equipar el espacio de tu mascota.",
        "Fácil de usar, incluso si es tu primera mascota.",
        "Pensado para el juego, el descanso o el cuidado de tu mascota.",
        "Ideal si buscas practicidad en el día a día con mascotas.",
        "Una opción práctica para el bienestar de perros y gatos.",
        "Fácil de guardar y de tener siempre listo para usar.",
    ],
    "Herramientas": [
        "Pensado para resolver trabajos del día a día en casa o taller.",
        "Ideal para tener siempre a la mano en tu caja de herramientas.",
        "Una opción práctica para reparaciones y proyectos caseros.",
        "Fácil de usar, incluso si no eres un experto.",
        "Pensado para el bricolaje y las reparaciones del hogar.",
        "Ideal si buscas algo funcional para tus proyectos caseros.",
        "Una alternativa práctica frente a herramientas más costosas.",
        "Fácil de guardar en tu caja o estuche de herramientas.",
        "Pensado para quienes hacen reparaciones frecuentes en casa.",
        "Ideal para regalar a quien disfruta el bricolaje.",
        "Una opción práctica para tener lista para cualquier arreglo.",
        "Fácil de usar, sin necesitar experiencia previa.",
        "Pensado para sumar practicidad a tus proyectos de bricolaje.",
        "Ideal si buscas renovar tu set de herramientas.",
        "Una alternativa accesible para equipar mejor tu taller.",
        "Fácil de transportar a donde la necesites.",
        "Pensado para el uso frecuente en casa o en el taller.",
        "Ideal para quienes buscan practicidad al hacer reparaciones.",
        "Una opción práctica para tu taller, sin gastar de más.",
        "Fácil de usar desde la primera vez que la pruebes.",
    ],
    "Fiesta y Piñatería": [
        "Ideal para darle vida a tu próxima celebración.",
        "Pensado para que tu fiesta quede completa sin complicarte.",
        "Una opción práctica para decorar cualquier celebración.",
        "Fácil de combinar con la temática de tu evento.",
        "Pensado para cumpleaños, piñatas o celebraciones especiales.",
        "Ideal si buscas decorar sin gastar de más.",
        "Una alternativa práctica frente a decoraciones más costosas.",
        "Fácil de armar y de usar el mismo día del evento.",
        "Pensado para sumar color y diversión a tu celebración.",
        "Ideal para regalar o para armar la fiesta perfecta.",
        "Una opción práctica para completar la decoración de tu evento.",
        "Fácil de combinar con otros elementos de fiesta.",
        "Pensado para celebraciones infantiles o de adultos.",
        "Ideal si buscas algo llamativo para tu próxima fiesta.",
        "Una alternativa accesible para decorar sin complicarte.",
        "Fácil de transportar y de montar el día del evento.",
        "Pensado para que la celebración quede como la imaginaste.",
        "Ideal para quienes organizan fiestas con frecuencia.",
        "Una opción práctica para sumar a la decoración de tu evento.",
        "Fácil de usar, pensado para que la fiesta no falte detalle.",
    ],
    "Papelería": [
        "Ideal para el estudio, la oficina o el uso diario.",
        "Pensado para tener siempre a la mano en el escritorio.",
        "Una opción práctica para organizar tus tareas o proyectos.",
        "Fácil de usar en casa, la oficina o el colegio.",
        "Pensado para estudiantes, profesionales o quien lo necesite.",
        "Ideal si buscas organizar mejor tu día a día.",
        "Una alternativa práctica frente a opciones más costosas.",
        "Fácil de guardar en tu mochila, cartuchera o escritorio.",
        "Pensado para el estudio o el trabajo diario.",
        "Ideal para regalar a estudiantes o amantes de la papelería.",
        "Una opción práctica para tener siempre lista para usar.",
        "Fácil de usar desde el primer día de clases o trabajo.",
        "Pensado para sumar orden a tus tareas diarias.",
        "Ideal si buscas renovar tus útiles de estudio u oficina.",
        "Una alternativa accesible para equipar tu escritorio.",
        "Fácil de transportar a donde estudies o trabajes.",
        "Pensado para el uso frecuente en el colegio o la oficina.",
        "Ideal para quienes buscan practicidad al organizar sus tareas.",
        "Una opción práctica para tu escritorio, sin gastar de más.",
        "Fácil de usar desde la primera vez que la pruebes.",
    ],
    "Seguridad": [
        "Pensado para darte tranquilidad en el día a día.",
        "Ideal para reforzar la seguridad de tu casa o negocio.",
        "Una opción práctica para tener siempre a la mano.",
        "Fácil de instalar o de llevar contigo.",
        "Pensado para quienes buscan más tranquilidad en casa.",
        "Ideal si buscas reforzar la seguridad sin complicarte.",
        "Una alternativa práctica frente a sistemas más costosos.",
        "Fácil de usar, incluso sin experiencia previa.",
        "Pensado para el cuidado de tu hogar, negocio o familia.",
        "Ideal para regalar a quien valora la seguridad personal.",
        "Una opción práctica para sumar tranquilidad a tu rutina.",
        "Fácil de instalar, sin necesitar un técnico.",
        "Pensado para tener siempre a la mano en casa o al salir.",
        "Ideal si buscas algo funcional para reforzar tu seguridad.",
        "Una alternativa accesible frente a soluciones más costosas.",
        "Fácil de usar en situaciones cotidianas.",
        "Pensado para el día a día, en casa o fuera de ella.",
        "Ideal para quienes buscan practicidad al reforzar su seguridad.",
        "Una opción práctica para sumar a tu kit de seguridad.",
        "Fácil de llevar contigo a donde vayas.",
    ],
    "Bienestar Íntimo": [
        "Pensado para tu bienestar personal, con discreción en el envío.",
        "Ideal para quienes buscan cuidar de su bienestar íntimo.",
        "Una opción práctica y discreta para tu día a día.",
        "Fácil de usar, pensado para tu comodidad.",
        "Pensado para sumar a tu bienestar personal, con total discreción.",
        "Ideal si buscas cuidar de ti sin complicaciones.",
        "Una alternativa práctica para tu bienestar íntimo.",
        "Fácil de incorporar a tu rutina personal.",
        "Pensado para tu comodidad, con empaque discreto.",
        "Ideal para quienes priorizan su bienestar personal.",
        "Una opción práctica para sumar a tu cuidado íntimo.",
        "Fácil de usar, sin complicarte con instrucciones largas.",
        "Pensado para acompañarte en tu bienestar, con total privacidad.",
        "Ideal si buscas algo práctico para tu cuidado personal.",
        "Una alternativa accesible para tu bienestar íntimo.",
        "Fácil de guardar, pensado para tu privacidad.",
        "Pensado para el día a día, con envío siempre discreto.",
        "Ideal para quienes buscan comodidad y privacidad.",
        "Una opción práctica para tu bienestar personal diario.",
        "Fácil de usar desde el primer momento.",
    ],
    "Juguetes": [
        "Ideal para regalar o para sumar horas de diversión en casa.",
        "Pensado para que los más pequeños se diviertan sin parar.",
        "Una opción práctica para regalar en cualquier ocasión.",
        "Fácil de usar, pensado para la diversión de los niños.",
        "Pensado para sumar horas de juego en casa o al aire libre.",
        "Ideal para regalar en cumpleaños o cualquier celebración.",
        "Una alternativa práctica frente a juguetes más costosos.",
        "Fácil de guardar cuando termine el momento de juego.",
        "Pensado para estimular la imaginación de los más pequeños.",
        "Ideal si buscas algo entretenido para regalar.",
        "Una opción práctica para sumar diversión al día a día.",
        "Fácil de usar, pensado para distintas edades.",
        "Pensado para compartir en familia o entre amigos.",
        "Ideal para regalar a quien disfruta jugar en casa.",
        "Una alternativa accesible para sumar a la juguetera.",
        "Fácil de transportar, ideal también para salidas.",
        "Pensado para el juego diario, en casa o fuera de ella.",
        "Ideal para quienes buscan algo divertido y práctico.",
        "Una opción práctica para sumar horas de entretenimiento.",
        "Fácil de usar desde el primer momento de juego.",
    ],
    "Otros": GENERIC_BENEFITS,
}

TRUST_CLOSERS: list[str] = [
    "Pagas contra entrega y recibes en todo México.",
    "Compra protegida: pagas solo cuando recibes tu pedido.",
    "Envío a todo México, con pago contra entrega.",
    "Recíbelo en tu casa y paga contra entrega, sin adelantos.",
    "Entrega a nivel nacional, pagas cuando el pedido llega a tu puerta.",
    "Compra sin riesgo: pago contra entrega en todo el país.",
    "Envío nacional y pago contra entrega, como en toda Pegasus Store.",
    "Llega a tu puerta y pagas contra entrega, sin sorpresas.",
    "Pedido con pago contra entrega, disponible en todo México.",
    "Recibes primero, pagas después — así de simple.",
    "Cobertura nacional y pago contra entrega, sin letras chiquitas.",
    "Haces tu pedido y pagas cuando el repartidor te lo entrega.",
    "Sin pagos anticipados: pagas al recibir tu pedido en la puerta.",
    "Entrega en todo México, con la tranquilidad del pago contra entrega.",
    "Pegasus Store te lo lleva a la puerta, pagas al recibir.",
    "Compra tranquilo: solo pagas si el pedido llega bien a tus manos.",
    "Pedido a domicilio con pago contra entrega en todo el territorio nacional.",
    "Te lo entregamos en casa y pagas ahí mismo, sin anticipos.",
    "Envíos a todo México con la opción de pago contra entrega.",
    "Recibe tu pedido y paga en el momento de la entrega.",
    "Compra respaldada: pagas contra entrega, en cualquier ciudad del país.",
    "Pide hoy, paga cuando lo tengas en tus manos.",
    "Pagas cuando el pedido está en tus manos, no antes.",
]


def is_generated_description(text: str) -> bool:
    """True si description_unique salió de estas plantillas (termina en una de
    las TRUST_CLOSERS). La ficha y Google no la usan: es la misma estructura
    repetida en miles de productos, lo que Google trata como contenido hecho
    en masa. Un texto escrito a mano en el admin sí se muestra."""
    return (text or "").strip().endswith(tuple(TRUST_CLOSERS))


def generate_unique_content(product) -> dict:
    """Genera {meta_title, meta_description, description_unique} para un
    producto, por plantillas deterministas — ver docstring del módulo.
    No llama a ningún servicio externo. Nunca falla: si no hay ancla real
    ni atributos, usa solo nombre/categoría/precio/plantillas.

    Llamar solo sobre productos con has_usable_name(product.name) — un
    nombre basura (p. ej. "..") no debería recibir contenido "único"
    generado sobre él."""
    pk = product.pk or 0
    name = _clean_name(product.name)
    category_label = product.category.name if product.category_id else "nuestro catálogo"

    opener = _pick(OPENERS, pk, 0).format(name=name, category=category_label)
    benefits = CATEGORY_BENEFITS.get(category_label, GENERIC_BENEFITS)
    benefit = _pick(benefits, pk, 17)
    closer = _pick(TRUST_CLOSERS, pk, 41)

    anchor = extract_anchor_sentence(product.description)
    attribute_clause = _attribute_clause(product)

    parts = [opener, benefit]
    if anchor:
        parts.append(f"Entre sus características: {anchor}")
    if attribute_clause:
        parts.append(attribute_clause)
    parts.append(closer)
    description_unique = " ".join(parts)

    meta_title = Truncator(f"{name} | {category_label}").chars(70, truncate="")
    # meta_description prioritizes the real anchor over the generic benefit
    # line when one exists — it's the field Google shows in search results,
    # so it's the one where uniqueness matters most.
    meta_body = anchor if anchor else benefit
    meta_description = Truncator(f"{name}: {meta_body} {closer}").chars(160, truncate=" …")

    return {
        "meta_title": meta_title,
        "meta_description": meta_description,
        "description_unique": description_unique,
    }
