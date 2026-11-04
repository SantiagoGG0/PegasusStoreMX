import json
import re
import unicodedata
from html import unescape

from django.utils.html import escape


ISSUE_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("drive_link", re.compile(r"\b(?:drive\.google|docs\.google|google\s+drive|drive)\b", re.I)),
    ("telegram_link", re.compile(r"\b(?:t\.me|telegram)\b", re.I)),
    ("youtube_link", re.compile(r"\b(?:youtube\.com|youtu\.be|youtube\s+shorts?)\b", re.I)),
    ("whatsapp_group", re.compile(r"\b(?:chat\.whatsapp\.com|comunidad\s+whatsapp|grupo\s+whatsapp)\b", re.I)),
    ("supplier_social", re.compile(r"\b(?:siguenos|canal|grupo|comunidad|whatsapp|mensaje\s+por\s+interno)\b", re.I)),
    ("supplier_resources", re.compile(r"\b(?:recursos?\s+adicionales?|imagenes?\s+de\s+apoyo|catalogo|catalogos)\b", re.I)),
    ("supplier_stock_notice", re.compile(r"\b(?:agotados?|reposicion|stock|nuevos?\s+productos?)\b", re.I)),
    ("supplier_warranty", re.compile(r"\b(?:garantia|defectos?\s+de\s+fabrica|devolucion|empaque\s+original|manuales?)\b", re.I)),
    ("supplier_sales", re.compile(r"\b(?:ventas?\s+al\s+por\s+mayor|mayoristas?|importaciones?)\b", re.I)),
    ("supplier_phone", re.compile(r"(?:\+?57[\s.-]?)?(?:3\d{2}[\s.-]?\d{3}[\s.-]?\d{4})")),
    ("external_url", re.compile(r"\b(?:https?://|www\.)", re.I)),
)

HTML_BLOCK_RE = re.compile(r"</?(?:p|div|li|ul|ol|br|h[1-6]|section|article|blockquote)[^>]*>", re.I)
SCRIPT_STYLE_RE = re.compile(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def find_description_issues(description: str) -> list[str]:
    """Return issue ids found in raw supplier description text."""
    text = description or ""
    issues: list[str] = []
    if _is_editor_json(text):
        issues.append("json_doc")
    for issue_id, pattern in ISSUE_PATTERNS:
        if pattern.search(text):
            issues.append(issue_id)
    return issues


def sanitize_product_description(description: str) -> str:
    """Remove supplier-only content and return escaped paragraph HTML."""
    text = _extract_editor_text(description) if _is_editor_json(description or "") else description or ""
    lines = _to_lines(text)

    cleaned_lines: list[str] = []
    for line in lines:
        compact = re.sub(r"\s+", " ", line).strip()
        if not compact:
            continue
        if _line_has_supplier_content(compact):
            continue
        cleaned_lines.append(compact)

    return "\n".join(f"<p>{escape(line)}</p>" for line in cleaned_lines)


def _is_editor_json(value: str) -> bool:
    text = (value or "").strip()
    return text.startswith("{") and '"type"' in text and '"doc"' in text


def _extract_editor_text(value: str) -> str:
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return value or ""

    parts: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str):
                parts.append(text)
            for child in node.get("content") or []:
                walk(child)
            if node.get("type") in {"paragraph", "heading", "listItem"}:
                parts.append("\n")
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload)
    return " ".join(parts).replace(" \n ", "\n").replace("\n ", "\n").replace(" \n", "\n")


def _to_lines(value: str) -> list[str]:
    text = SCRIPT_STYLE_RE.sub(" ", value or "")
    text = HTML_BLOCK_RE.sub("\n", text)
    text = TAG_RE.sub(" ", text)
    text = unescape(text)
    return [line.strip() for line in re.split(r"[\r\n]+", text)]


def _line_has_supplier_content(line: str) -> bool:
    searchable = _strip_accents(line)
    return any(pattern.search(searchable) for _, pattern in ISSUE_PATTERNS)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii")


# ── Descripción para mostrar en la ficha ─────────────────────────────────────
# El import ya pasa sanitize_product_description, pero muchas descripciones
# llegan en un solo párrafo (o se importaron antes del sanitizador) y traen
# la garantía del proveedor ("10 días… daños por terceros no cubre"), que
# contradice la garantía legal que ofrece la tienda. Aquí se corta por
# oración, no por párrafo, para no perder las características.

# Rótulo que abre una sección de políticas del proveedor ("Garantía:", "Nota:",
# y también "GARANTÍA1." pegado al texto anterior, sin dos puntos).
_POLICY_LABEL = re.compile(r"\b(?:garantia\s*\d*\s*[:.]|(?:nota|importante|politicas?)\s*:)", re.I)
_POLICY_WORDS = re.compile(r"garanti(?!z)|devoluc|defecto|terceros|reclam|cambio|reporta|cubre|mal uso|manipulaci", re.I)
# Oraciones que no se muestran nunca. "garanti(?!z)" cubre garantía, garantías,
# "GARANTÍAN" (errata) y "GARANTÍA1", pero no "garantiza".
_DISPLAY_DROP = re.compile(
    r"garanti(?!z)|defectos?\s+de\s+fabrica|danos?\s+ocasionad|por\s+terceros|devoluci|reclamo|reportar"
    r"|\bdropi\b|https?://|www\.|t\.me|telegram|whatsapp|mayoristas?|al\s+por\s+mayor|proveedor"
    r"|recursos?\s+adicionales?|(?:\+?57[\s.-]?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}",
    re.I,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡0-9])")
_LABELED = re.compile(r"^([^:]{3,45}):\s*(.+)$", re.S)
_GENERIC_LABELS = {
    "descripcion", "descripcion del producto", "caracteristicas", "caracteristicas principales", "funciones",
    "especificaciones", "especificaciones tecnicas", "beneficios", "incluye", "contenido", "contenido del paquete",
    "nota", "modo de uso", "tipo de producto", "detalles", "ficha tecnica", "informacion", "el paquete incluye",
}
HIGHLIGHTS_MAX = 4


def clean_description_for_display(description: str) -> list[str]:
    """Párrafos de texto plano listos para mostrar (sin HTML)."""
    text = _extract_editor_text(description) if _is_editor_json(description or "") else description or ""
    paragraphs: list[str] = []
    for line in _to_lines(text):
        compact = re.sub(r"\s+", " ", line).strip()
        if not compact:
            continue
        searchable = _strip_accents(compact)
        for match in _POLICY_LABEL.finditer(searchable):
            if _POLICY_WORDS.search(searchable[match.end():match.end() + 160]):
                compact = compact[:match.start()].strip()
                break
        sentences = [
            s.strip() for s in _SENTENCE_SPLIT.split(compact)
            if s.strip() and not _DISPLAY_DROP.search(_strip_accents(s))
        ]
        if sentences:
            paragraphs.append(" ".join(sentences))
    return paragraphs


def _label_highlight(chunk: str, name_tokens: set[str]) -> str:
    match = _LABELED.match(chunk)
    if not match:
        return ""
    label, rest = match.group(1).strip(" -•*"), match.group(2).strip()
    norm = _strip_accents(label).lower().strip()
    if norm in _GENERIC_LABELS:
        return _label_highlight(rest, name_tokens)
    words = norm.split()
    if not (1 <= len(words) <= 7) or ":" in rest[:40]:
        return ""
    if name_tokens and (len(set(words) & name_tokens) >= 2 or words[0] in name_tokens):
        return ""  # el rótulo es el nombre del producto ("Consola Retro Portátil:")
    if len(rest) <= 40 and ":" not in rest:
        return f"{label}: {rest.rstrip('.')}"
    return label


def extract_highlights(paragraphs: list[str], product_name: str = "") -> list[str]:
    """Hasta HIGHLIGHTS_MAX puntos clave ("Pantalla IPS de alta definición",
    "Batería de 4000 mAh") tomados de los rótulos que ya traen las
    descripciones. Sin al menos dos, no se muestra nada."""
    name_tokens = set(_strip_accents(product_name).lower().split())
    found: list[str] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        for chunk in _SENTENCE_SPLIT.split(paragraph):
            highlight = _label_highlight(chunk.strip(), name_tokens)
            key = _strip_accents(highlight).lower()
            if highlight and key not in seen:
                seen.add(key)
                found.append(highlight[:80])
            if len(found) >= HIGHLIGHTS_MAX:
                return found
    return found if len(found) >= 2 else []
