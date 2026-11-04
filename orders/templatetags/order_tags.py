from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def cancel_seconds_remaining(order):
    if not order.can_cancel():
        return 0
    delta = order.cancel_deadline - timezone.now()
    return max(0, int(delta.total_seconds()))
