import re
from django import template

register = template.Library()

# Matches trailing SKU-like tokens: all-caps with digits/hyphens, e.g. "Jtx22-2-C", "DL-9302", "BL-XL-001"
_SKU_RE = re.compile(r'\s+[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+){1,}$')


@register.filter
def clean_product_name(value):
    """Remove trailing SKU codes from product names for display."""
    if not value:
        return value
    return _SKU_RE.sub('', str(value)).strip()
