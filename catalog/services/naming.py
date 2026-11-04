"""
Nombre visible de un producto (Product.display_name).

Dropi corta los nombres en 40 caracteres ("Organizador Maquillaje Acrílico
Giratori"), los proveedores agregan etiquetas internas ("DROPI CUP") y
emojis, y muchos vienen en MAYÚSCULAS. Este módulo arma un nombre limpio para
mostrar sin tocar Product.name, que sigue siendo el de Dropi (sincronización,
pedidos y slugs dependen de él).

- clean_display_name(name)            → limpieza básica, sin contexto.
- clean_display_name(name, vocab)     → además quita la última palabra
  cuando el nombre llegó cortado en el límite y esa palabra no existe
  completa en ningún otro nombre del catálogo.

Funciones puras (sin Django) para poder probarlas y usarlas en scripts.
"""
from __future__ import annotations

import re
import unicodedata

DROPI_NAME_LIMIT = 40
DISPLAY_NAME_MAX = 120

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000200D\U000020E3\U00002190-\U000021FF\U0000231A-\U0000231B•▪●★☆✔✖✨]+"
)
# Etiquetas internas de proveedores / Dropi que no le dicen nada al comprador.
_INTERNAL_TAGS = re.compile(r"\bdropi\s*cup\b\.?|\bdropi\b", re.I)
_WS = re.compile(r"\s+")
# Prefijos del proveedor: códigos ("000901-", "0010-") y gritos de venta
# ("¡ÚLTIMAS UNIDADES!", "¡EN LIQUIDACIÓN!") que no son parte del nombre.
_SKU_PREFIX = re.compile(r"^\s*(?:\d{3,}\s*[-–]\s*)+(?:\d{3,}\s+)*")
_PROMO_TAG = re.compile(r"¡\s*(?:ultimas?|últimas?|en\s+)?\s*(?:unidades|liquidaci[oó]n|tendencia|oferta|promo(?:ci[oó]n)?|nuevo)\s*!", re.I)
_TOKEN = re.compile(r"[a-z0-9]+")

# Palabras que no pueden cerrar un nombre ("Set Destornillador Con", "+").
_TRAILING_JUNK = {
    "con", "de", "del", "la", "el", "los", "las", "para", "por", "y", "e", "o", "u", "en", "a", "al",
    "sin", "tipo", "x", "+", "-", "/", "&", ",", "|",
}
_LOWER_WORDS = {"de", "del", "la", "el", "los", "las", "para", "por", "y", "e", "o", "u", "en", "a", "al", "con", "sin", "x"}


def normalize_token(word: str) -> str:
    text = unicodedata.normalize("NFKD", word.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def name_tokens(name: str) -> list[str]:
    return _TOKEN.findall(normalize_token(name or ""))


VOCAB_MIN_COUNT = 3


def build_vocabulary(names) -> set[str]:
    """Palabras que aparecen completas en el catálogo (al menos
    VOCAB_MIN_COUNT veces): todas menos la última de los nombres que
    llegaron cortados en el límite de Dropi. Con una sola aparición también
    entran restos de cortes viejos ("Est", "Grand")."""
    counts: dict[str, int] = {}
    for name in names:
        tokens = name_tokens(name)
        if len((name or "").strip()) >= DROPI_NAME_LIMIT and tokens:
            tokens = tokens[:-1]
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
    return {token for token, n in counts.items() if n >= VOCAB_MIN_COUNT}


# Siglas que siempre van en mayúsculas, vengan como vengan.
_ACRONYMS = {
    "led", "usb", "hd", "fhd", "uhd", "rgb", "tv", "pc", "sd", "gps", "lcd", "uv", "ac", "dc", "xl", "xxl", "xs",
    "abs", "pvc", "ip", "mp3", "mp4", "hdmi", "ips", "nfc", "4k", "8k", "2k", "3d", "ac/dc", "usb-c", "tws", "ufo",
}
_UNIT = re.compile(r"^(\d+(?:[.,]\d+)?)(cm|mm|m|ml|l|lt|kg|g|gr|mah|w|v|hz|pulg|oz|gb|tb|mb)$", re.I)
_QUANTITY = re.compile(r"^x\d+$", re.I)


def _capitalize(word: str) -> str:
    """Mayúscula en la primera letra, aunque la palabra empiece con "¡" o "(".
    El resto en minúscula."""
    lower = word.lower()
    for i, ch in enumerate(lower):
        if ch.isalpha():
            return lower[:i] + ch.upper() + lower[i + 1:]
    return lower


def _smart_case(word: str, first: bool, mostly_upper: bool) -> str:
    letters = [c for c in word if c.isalpha()]
    if not letters:
        return word
    lower = word.lower()
    parts = [p for p in lower.split("/") if p]
    if parts and all(p in _ACRONYMS for p in parts):  # "led", "usb/sd"
        return word.upper()
    if not first and lower in _LOWER_WORDS:
        return lower
    if _QUANTITY.match(word):
        return lower
    unit = _UNIT.match(word)
    if unit:
        number, suffix = unit.groups()
        return number + (suffix.upper() if suffix.lower() in {"w", "v", "gb", "tb", "mb"} else suffix.lower())
    if any(c.isdigit() for c in word):
        # Modelos (M25, YG300, FK23D-210, W26) en mayúsculas; palabras con
        # un número pegado ("Cargador20w", "Pro2+") como palabra normal.
        return word.upper() if len(letters) <= 3 else _capitalize(word)
    if not mostly_upper and word.isupper() and len(letters) <= 4:
        return word  # sigla que el proveedor escribió a propósito: "PSP"
    if not mostly_upper and any(c.isupper() for c in word[1:]) and not word.isupper():
        return word  # mezcla intencional: "iPhone", "FLIp6"
    return _capitalize(word)


def _case_name(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    mostly_upper = bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.6
    return " ".join(_smart_case(word, i == 0, mostly_upper) for i, word in enumerate(text.split(" ")))


def clean_display_name(name: str, vocab: set[str] | None = None) -> str:
    raw = (name or "").strip()
    text = _EMOJI.sub(" ", raw)
    text = _INTERNAL_TAGS.sub(" ", text)
    text = _PROMO_TAG.sub(" ", text)
    text = _SKU_PREFIX.sub("", text.lstrip(" *#_-"))
    text = text.replace('"', " ").replace("“", " ").replace("”", " ")
    text = _WS.sub(" ", text).strip(" .,-–—|/+&*#_")

    words = text.split(" ")
    if len(raw) >= DROPI_NAME_LIMIT and len(words) > 2:
        last = name_tokens(words[-1])
        cut = bool(last) and not last[-1].isdigit() and (
            len(last[-1]) <= 2 or (vocab is not None and last[-1] not in vocab)
        )
        if cut:
            words = words[:-1]
    while len(words) > 2:
        tail = normalize_token(words[-1]).strip(".,")
        if tail not in _TRAILING_JUNK and not (len(tail) == 1 and tail.isalpha()):
            break
        words = words[:-1]  # conector o letra suelta al final: "… Inodoro D"
    text = " ".join(words).strip(" .,-–—|/+&")
    if not text:
        return raw[:DISPLAY_NAME_MAX]
    return _case_name(text)[:DISPLAY_NAME_MAX]
