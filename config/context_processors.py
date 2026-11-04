from django.conf import settings

from .site import site_base_url


def analytics(request):
    return {
        "GA4_MEASUREMENT_ID": getattr(settings, "GA4_MEASUREMENT_ID", ""),
        "META_PIXEL_ID": getattr(settings, "META_PIXEL_ID", ""),
        "TIKTOK_PIXEL_ID": getattr(settings, "TIKTOK_PIXEL_ID", ""),
        "GOOGLE_ADS_PURCHASE_SEND_TO": getattr(settings, "GOOGLE_ADS_PURCHASE_SEND_TO", ""),
        "GOOGLE_ADS_ID": getattr(settings, "GOOGLE_ADS_ID", ""),
        "CLARITY_PROJECT_ID": getattr(settings, "CLARITY_PROJECT_ID", ""),
    }


def site(request):
    """SITE_URL: base canónica para canonical, og:url y og:image."""
    return {"SITE_URL": site_base_url(request)}
