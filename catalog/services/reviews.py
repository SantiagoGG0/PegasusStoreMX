"""
Reseñas de producto: escritura, recálculo de agregados y reglas de borde.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Avg, Count

from catalog.models import Product, ProductReview

User = get_user_model()

MIN_SCORE = 1
MAX_SCORE = 5


def recalculate_product_rating(product_id: int) -> None:
    """Actualiza rating_average y rating_count en Product desde reseñas publicadas."""
    agg = ProductReview.objects.filter(
        product_id=product_id,
        is_published=True,
    ).aggregate(avg=Avg("score"), cnt=Count("id"))

    cnt = agg["cnt"] or 0
    avg = agg["avg"]

    if cnt and avg is not None:
        average = Decimal(str(avg)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    else:
        average = None

    Product.objects.filter(pk=product_id).update(
        rating_average=average,
        rating_count=cnt,
    )


def user_can_review_product(user, product: Product) -> bool:
    """Solo clientes autenticados que compraron el producto (no staff por defecto)."""
    if not getattr(user, "is_authenticated", False):
        return False
    return user_has_purchased_product(user, product)


def user_has_purchased_product(user, product: Product) -> bool:
    """
    Pedidos no cancelados del usuario (o guest con mismo email vinculado).
    Order.items: product_id, local_id o dropi_id.
    """
    from django.db.models import Q

    from orders.models import Order

    email = (getattr(user, "email", None) or "").strip()
    ownership = Q(user=user)
    if email:
        ownership |= Q(user__isnull=True, email__iexact=email)

    orders = (
        Order.objects.exclude(status=Order.STATUS_CANCELLED)
        .filter(ownership)
        .only("items")
    )
    product_pk = str(product.pk)
    dropi_id = str(product.dropi_id)

    for order in orders.iterator():
        for item in order.items or []:
            if not isinstance(item, dict):
                continue
            for key in ("product_id", "local_id"):
                if str(item.get(key, "")) == product_pk:
                    return True
            if str(item.get("dropi_id", "")) == dropi_id:
                return True
            if str(item.get("id", "")) == dropi_id:
                return True
    return False


def get_user_review(user, product: Product) -> ProductReview | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return ProductReview.objects.filter(product=product, user=user).first()


def get_published_reviews(product: Product, *, limit: int = 20):
    return (
        ProductReview.objects.filter(product=product, is_published=True)
        .select_related("user", "product")
        .order_by("-created_at")[:limit]
    )


@transaction.atomic
def submit_review(
    *,
    product: Product,
    user,
    score: int,
    comment: str = "",
    is_published: bool = True,
) -> ProductReview:
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise ValidationError({"score": "La puntuación debe estar entre 1 y 5."})

    if not user_can_review_product(user, product):
        raise PermissionDenied("No puedes reseñar este producto.")

    review, _created = ProductReview.objects.update_or_create(
        product=product,
        user=user,
        defaults={
            "score": score,
            "comment": (comment or "").strip(),
            "is_published": is_published,
        },
    )
    recalculate_product_rating(product.pk)
    return review


@transaction.atomic
def delete_review(*, review: ProductReview) -> None:
    product_id = review.product_id
    review.delete()
    recalculate_product_rating(product_id)


def _get_purchased_product_ids(user) -> tuple[set[int], set[int]]:
    """Returns (local_pks, dropi_ids) of all products the user has purchased."""
    from django.db.models import Q

    from orders.models import Order

    if not getattr(user, "is_authenticated", False):
        return set(), set()

    email = (getattr(user, "email", None) or "").strip()
    ownership = Q(user=user)
    if email:
        ownership |= Q(user__isnull=True, email__iexact=email)

    orders = (
        Order.objects.exclude(status=Order.STATUS_CANCELLED)
        .filter(ownership)
        .only("items")
    )
    pks: set[int] = set()
    dropi_ids: set[int] = set()
    for order in orders.iterator():
        for item in order.items or []:
            if not isinstance(item, dict):
                continue
            for key in ("product_id", "local_id"):
                val = item.get(key)
                if val:
                    try:
                        pks.add(int(val))
                    except (TypeError, ValueError):
                        pass
            for key in ("dropi_id", "id"):
                val = item.get(key)
                if val:
                    try:
                        dropi_ids.add(int(val))
                    except (TypeError, ValueError):
                        pass
    return pks, dropi_ids


def get_dashboard_review_data(user, *, limit: int = 20) -> tuple[list, list]:
    """
    Returns (pending, my_reviews):
      - pending: list[Product] — bought but not yet reviewed
      - my_reviews: list[ProductReview] — user's submitted reviews with product info
    """
    if not getattr(user, "is_authenticated", False):
        return [], []

    my_reviews = list(
        ProductReview.objects.filter(user=user)
        .select_related("product")
        .order_by("-created_at")
    )
    reviewed_product_ids = {r.product_id for r in my_reviews}

    pks, dropi_ids = _get_purchased_product_ids(user)
    if not pks and not dropi_ids:
        return [], my_reviews

    from django.db.models import Q as DQ

    q = DQ(pk__in=pks)
    if dropi_ids:
        q |= DQ(dropi_id__in=dropi_ids)

    purchased = list(
        Product.objects.filter(q, is_active=True)
        .exclude(slug="")
        .order_by("-id")
    )
    pending = [p for p in purchased if p.pk not in reviewed_product_ids][:limit]

    return pending, my_reviews


# ── Reseñas desde el pedido (sin cuenta) ─────────────────────────────────────
# Casi todos los pedidos contra entrega son de invitados: sin esta vía la
# tienda no junta opiniones. El enlace del pedido (access_token UUID) ya es
# la credencial del cliente para ver y cancelar su pedido; con el pedido
# entregado, también sirve para opinar sobre lo que compró.


def order_can_be_reviewed(order) -> bool:
    from orders.models import Order

    return order.status == Order.STATUS_DELIVERED


def products_in_order(order) -> list[Product]:
    """Productos del pedido, en el orden de order.items, sin repetidos."""
    pks: list[int] = []
    dropi_ids: list[int] = []
    for item in order.items or []:
        if not isinstance(item, dict):
            continue
        for key, bucket in (("local_id", pks), ("product_id", pks), ("dropi_id", dropi_ids)):
            try:
                value = int(item.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value:
                bucket.append(value)
    from django.db.models import Q

    found = list(Product.objects.filter(Q(pk__in=pks) | Q(dropi_id__in=dropi_ids)).exclude(slug=""))
    rank = {pk: i for i, pk in enumerate(pks)}
    found.sort(key=lambda p: rank.get(p.pk, len(rank)))
    return found


def public_author_name(name: str, surname: str = "") -> str:
    first = (name or "").strip().split(" ")[0].title()
    initial = (surname or "").strip()[:1].upper()
    if not first:
        return "Cliente"
    return f"{first} {initial}." if initial else first


@transaction.atomic
def submit_order_review(*, order, product: Product, score: int, comment: str = "") -> ProductReview:
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise ValidationError({"score": "La puntuación debe estar entre 1 y 5."})
    if not order_can_be_reviewed(order):
        raise PermissionDenied("Podrás opinar cuando el pedido esté entregado.")
    if product.pk not in {p.pk for p in products_in_order(order)}:
        raise PermissionDenied("Ese producto no está en este pedido.")

    review, _created = ProductReview.objects.update_or_create(
        product=product,
        order=order,
        defaults={
            "user": order.user if getattr(order, "user_id", None) else None,
            "score": score,
            "comment": (comment or "").strip()[:1500],
            "author_name": public_author_name(order.name, order.surname),
            "author_city": (order.city or "").strip().title()[:80],
            "is_published": True,
        },
    )
    recalculate_product_rating(product.pk)
    from django.core.cache import cache

    cache.delete_many(["store_review_summary_v1", "site_rating_average_v2"])
    return review


def get_store_reviews(*, limit: int = 6, exclude_product=None):
    """Reseñas recientes de toda la tienda (con comentario), para mostrar
    prueba social en el inicio, en Confianza y en fichas sin opiniones."""
    qs = (
        ProductReview.objects.filter(is_published=True)
        .exclude(comment="")
        .select_related("product", "user")
        .order_by("-created_at")
    )
    if exclude_product is not None:
        qs = qs.exclude(product=exclude_product)
    return list(qs[:limit])


def store_review_summary() -> dict:
    """{"average": 4.7 | None, "count": N} de todas las reseñas publicadas."""
    from django.core.cache import cache

    cached = cache.get("store_review_summary_v1")
    if cached is not None:
        return cached
    agg = ProductReview.objects.filter(is_published=True).aggregate(avg=Avg("score"), cnt=Count("id"))
    count = agg["cnt"] or 0
    average = round(float(agg["avg"]), 1) if count else None
    result = {"average": average, "count": count}
    cache.set("store_review_summary_v1", result, 1800)
    return result
