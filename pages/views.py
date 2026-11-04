import json
import logging

from django.utils.safestring import mark_safe
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)

LEGAL_DOCS = ["terminos", "privacidad", "devoluciones", "propiedad-intelectual"]

LEGAL_TABS = [
    {"key": "terminos", "label": "Términos y condiciones", "url_name": "pages:terms"},
    {"key": "privacidad", "label": "Política de privacidad", "url_name": "pages:privacy"},
    {"key": "devoluciones", "label": "Devoluciones y reembolsos", "url_name": "pages:refunds"},
    {"key": "propiedad-intelectual", "label": "Propiedad intelectual", "url_name": "pages:intellectual_property"},
]

LEGAL_TITLES = {
    "terminos": "Términos y condiciones",
    "privacidad": "Política de privacidad",
    "devoluciones": "Devoluciones y reembolsos",
    "propiedad-intelectual": "Propiedad intelectual",
}


def _json_ld(*nodes) -> str:
    return mark_safe(json.dumps({"@context": "https://schema.org", "@graph": list(nodes)}, ensure_ascii=False))


class TrustView(TemplateView):
    """¿Es confiable Pegasus Store? Solo datos comprobables: identidad legal,
    guías rastreables, cifras de pedidos entregados y reseñas reales."""

    template_name = "pages/trust.html"

    def get_context_data(self, **kwargs):
        from catalog.seo import organization_json_ld
        from catalog.services.faq import faq_json_ld, store_faq
        from catalog.services.reviews import get_store_reviews, store_review_summary
        from catalog.services.trust import delivery_stats, recent_guides

        context = super().get_context_data(**kwargs)
        faq = store_faq()
        context.update({
            "recent_guides": recent_guides(),
            "delivery_stats": delivery_stats(),
            "store_reviews": get_store_reviews(limit=6),
            "review_summary": store_review_summary(),
            "faq_items": faq,
            "json_ld": _json_ld(organization_json_ld(self.request), faq_json_ld(faq)),
        })
        return context


class AboutView(TemplateView):
    template_name = "pages/about.html"

    def get_context_data(self, **kwargs):
        from catalog.seo import organization_json_ld
        from catalog.services.trust import delivery_stats

        context = super().get_context_data(**kwargs)
        context["delivery_stats"] = delivery_stats()
        context["json_ld"] = _json_ld(organization_json_ld(self.request))
        return context


class LegalView(TemplateView):
    template_name = "pages/legal.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc = self.kwargs.get("doc", "terminos")
        if doc not in LEGAL_DOCS:
            doc = "terminos"
        context["active_doc"] = doc
        context["legal_title"] = LEGAL_TITLES[doc]
        context["legal_tabs"] = LEGAL_TABS
        return context
