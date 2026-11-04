"""
Consolidación SEO del catálogo (Search Console: "Duplicada: Google ha
elegido una canónica diferente" y "Rastreada: actualmente sin indexar").

1. Basura: "productos" que son servicios (envío prioritario, garantía,
   flete…) o con nombre roto ("product image product image…", "..") →
   seo_exclusion="b": fuera de listas, del sitemap, de campañas y noindex.
2. Duplicados: productos activos con el mismo nombre normalizado. Se elige
   el mejor (más fotos, más relevancia, más stock) y los demás declaran
   rel=canonical hacia él (canonical_product) y salen del sitemap. Siguen
   publicados y vendibles: el catálogo no se achica, Google indexa una
   ficha por producto en vez de repartir la señal entre copias.
3. Protegidos: un producto que ya se vendió o cuyo slug está en
   data/seo_protected_slugs.txt (tráfico orgánico) nunca apunta a otra ficha
   (moverle la canónica a una página que Google ya posiciona le quita ese
   tráfico). Tampoco se vuelve el canónico del grupo: así no cambia la ficha
   principal que Google ya eligió para los demás.

Se recalcula entero en cada corrida (al final de cada vuelta de
catalog_worker y con `manage.py consolidate_seo`).
"""
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from catalog.models import Product

BATCH_SIZE = 500
JUNK_EXCLUSION = "b"
_JUNK_START = re.compile(r"^(envio|envios|garantia|flete|recargo)\b")
_JUNK_ANYWHERE = re.compile(r"\bproduct image\b")
_HAS_LETTERS = re.compile(r"[a-z]{2,}")
PROTECTED_SLUGS_FILE = Path(__file__).resolve().parent.parent / "data" / "seo_protected_slugs.txt"


def protected_product_ids() -> set[int]:
    """Productos vendidos (en algún pedido) + slugs con tráfico orgánico."""
    from orders.models import Order

    ids: set[int] = set()
    for items in Order.objects.values_list("items", flat=True):
        for item in items or []:
            if isinstance(item, dict) and str(item.get("product_id") or "").isdigit():
                ids.add(int(item["product_id"]))
    slugs = {
        line.strip() for line in PROTECTED_SLUGS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    ids |= set(Product.objects.filter(slug__in=slugs).values_list("pk", flat=True))
    return ids


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", (name or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def is_junk_name(name: str) -> bool:
    norm = normalize_name(name)
    return not _HAS_LETTERS.search(norm) or bool(_JUNK_START.search(norm) or _JUNK_ANYWHERE.search(norm))


def _main_score(product) -> tuple:
    images = len(product.images or [])
    return (images >= 2, product.rank_score, min(images, 5), product.stock, -product.pk)


def consolidate(apply: bool = False) -> dict:
    products = list(
        Product.objects.filter(is_active=True).only(
            "pk", "name", "images", "rank_score", "stock", "seo_exclusion", "canonical_product_id"
        )
    )
    protected = protected_product_ids()
    stats = {"junk": 0, "groups": 0, "canonicalized": 0, "uncanonicalized": 0}
    changed = {"seo_exclusion": [], "canonical_product": []}

    groups = defaultdict(list)
    for p in products:
        if is_junk_name(p.name):
            if not p.seo_exclusion:
                p.seo_exclusion = JUNK_EXCLUSION
                changed["seo_exclusion"].append(p)
                stats["junk"] += 1
            continue
        if p.seo_exclusion:
            continue  # ya excluido (noindex): no participa como canónico
        groups[normalize_name(p.name)].append(p)

    target_of: dict[int, int | None] = {}
    for members in groups.values():
        if len(members) == 1:
            target_of[members[0].pk] = None
            continue
        stats["groups"] += 1
        # La ficha principal que ya eligió una corrida anterior se mantiene
        # mientras siga activa en el grupo: si cambiara con el stock o la
        # relevancia, Google vería canonical nuevas en cada corrida.
        member_pks = {p.pk for p in members}
        current = Counter(p.canonical_product_id for p in members if p.canonical_product_id in member_pks)
        main = max(members, key=lambda p: (current.get(p.pk, 0), _main_score(p)))
        for p in members:
            target_of[p.pk] = None if p.pk == main.pk or p.pk in protected else main.pk

    for p in products:
        if p.pk not in target_of:
            continue
        target = target_of[p.pk]
        if p.canonical_product_id != target:
            stats["canonicalized" if target else "uncanonicalized"] += 1
            p.canonical_product_id = target
            changed["canonical_product"].append(p)

    if apply:
        for field, rows in changed.items():
            for i in range(0, len(rows), BATCH_SIZE):
                Product.objects.bulk_update(rows[i:i + BATCH_SIZE], [field])
    stats["duplicates_total"] = sum(1 for t in target_of.values() if t)
    return stats
