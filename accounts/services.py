from django.contrib.auth import get_user_model

from orders.models import Order

User = get_user_model()


def link_orders_to_user(user, email: str | None = None) -> int:
    """Associate guest orders with the user account by email."""
    lookup_email = (email or user.email or "").strip()
    if not lookup_email:
        return 0
    return Order.objects.filter(email__iexact=lookup_email, user__isnull=True).update(
        user=user
    )
