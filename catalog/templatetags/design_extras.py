import urllib.parse

from django import template

register = template.Library()

# Stable hue (0-359) per category label, used to tint category tiles/badges
# consistently across requests without storing a color field on the model.
_HUE_STEP = 47


@register.filter
def image_src(image):
    """URL de una entrada de Product.images (dict con url/image/src o texto)."""
    if isinstance(image, dict):
        return image.get("url") or image.get("image") or image.get("src") or ""
    return str(image or "")


@register.filter
def category_url(dropi_id):
    """{{ cat.dropi_id|category_url }} → /categoria/belleza/"""
    from catalog.seo import category_path

    return category_path(dropi_id)


@register.filter
def cat_hue(value):
    if not value:
        return 250
    total = sum(ord(ch) for ch in str(value))
    return (total * _HUE_STEP) % 360


@register.filter
def resize_img(url, size="400x400"):
    """Proxy an absolute image URL through images.weserv.nl for on-the-fly
    resize/compression, so multi-MB source photos (Dropi feed, uploads on
    S3/Cloudinary) aren't shipped at full resolution for small thumbnails.
    Relative paths (local filesystem media in dev, not publicly reachable
    by the proxy) pass through untouched."""
    if not url:
        return url
    url = str(url)
    if not url.startswith(("http://", "https://")):
        return url
    try:
        w, h = str(size).lower().split("x")
    except ValueError:
        w = h = size
    source = url.split("://", 1)[-1]
    encoded = urllib.parse.quote(source, safe="")
    return f"https://images.weserv.nl/?url={encoded}&w={w}&h={h}&fit=inside&we&q=75&output=webp"
