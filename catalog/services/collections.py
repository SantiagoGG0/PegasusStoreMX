"""
Colecciones por intención de búsqueda (catalog.models.Collection).

Un producto entra en una colección si su nombre contiene alguno de los
include_terms como palabras completas (sin tildes, sin importar mayúsculas y
también en plural/singular) y ninguno de los exclude_terms. La lista se guarda
en Collection.products (M2M) para que la página no tenga que revisar 40.000
nombres en cada visita; se recalcula al guardar en el admin, con
`manage.py refresh_collections` y sola cuando tiene más de un día.

Solo entran productos que pueden aparecer en listas: activos, con slug, sin
foto marcada, sin exclusión SEO y sin ser casi duplicados de otra ficha.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata

from django.db import connection, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

MIN_PRODUCTS_TO_PUBLISH = 8
STALE_AFTER_SECONDS = 24 * 3600
_refreshing = threading.Lock()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _variants(term: str) -> set[str]:
    """"organizador cocina" → también "organizadores cocina" (plural de la
    primera palabra) y "organizador cocinas". Suficiente para el catálogo."""
    words = normalize(term).split()
    if not words:
        return set()
    out = {" ".join(words)}
    for i, word in enumerate(words):
        forms = {word}
        if word.endswith("es") and len(word) > 4:
            forms.add(word[:-2])
        if word.endswith("s") and len(word) > 3:
            forms.add(word[:-1])
        elif word[-1] in "aeiou":
            forms.add(word + "s")
        else:
            forms.add(word + "es")
        for form in forms:
            out.add(" ".join(words[:i] + [form] + words[i + 1:]))
    return out


def _terms(raw: str) -> list[str]:
    return [t.strip() for t in (raw or "").splitlines() if t.strip()]


def compile_matcher(include_terms: str, exclude_terms: str = ""):
    include = set().union(*[_variants(t) for t in _terms(include_terms)]) if include_terms else set()
    exclude = set().union(*[_variants(t) for t in _terms(exclude_terms)]) if exclude_terms else set()

    def matches(name: str) -> bool:
        padded = f" {normalize(name)} "
        if not any(f" {term} " in padded for term in include):
            return False
        return not any(f" {term} " in padded for term in exclude)

    return matches


def eligible_products():
    from catalog.models import Product

    return (
        Product.objects.listable()
        .filter(is_active=True, image_flagged=False, canonical_product__isnull=True)
        .exclude(slug="")
    )


def refresh_collections(collections=None) -> dict[int, int]:
    """Recalcula los productos de las colecciones dadas (o de todas). Lee los
    nombres una sola vez. Devuelve {collection_id: cantidad}."""
    from catalog.models import Collection

    collections = list(collections) if collections is not None else list(Collection.objects.all())
    if not collections:
        return {}
    rows = list(eligible_products().values_list("pk", "name", "display_name"))
    now = timezone.now()
    counts = {}
    for collection in collections:
        matches = compile_matcher(collection.include_terms, collection.exclude_terms)
        pks = [pk for pk, name, shown in rows if matches(name) or (shown and matches(shown))]
        with transaction.atomic():
            collection.products.set(pks)
            collection.product_count = len(pks)
            collection.refreshed_at = now
            collection.save(update_fields=["product_count", "refreshed_at"])
        counts[collection.pk] = len(pks)
    return counts


def refresh_if_stale(collection) -> None:
    """Si la colección lleva más de un día sin recalcular, la recalcula en un
    hilo aparte (la visita no espera)."""
    if collection.refreshed_at and (timezone.now() - collection.refreshed_at).total_seconds() < STALE_AFTER_SECONDS:
        return
    if not _refreshing.acquire(blocking=False):
        return

    def run():
        try:
            refresh_collections([collection])
        except Exception:
            logger.exception("No se pudo recalcular la colección %s", collection.pk)
        finally:
            connection.close()
            _refreshing.release()

    threading.Thread(target=run, name=f"collection-{collection.pk}", daemon=True).start()


def collection_products(collection):
    """Productos de la colección para la página: con stock primero y por relevancia."""
    from django.db.models import Case, IntegerField, When

    return (
        eligible_products()
        .filter(collections=collection)
        .annotate(in_stock=Case(When(stock__gt=0, then=1), default=0, output_field=IntegerField()))
        .select_related("category")
        .prefetch_related("custom_images")
        .order_by("-in_stock", "-rank_score", "pk")
    )
