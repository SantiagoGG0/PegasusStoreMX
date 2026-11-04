from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "pages"

urlpatterns = [
    path("confianza/", views.TrustView.as_view(), name="trust"),
    path("quienes-somos/", views.AboutView.as_view(), name="about"),
    path("legal/terminos/", views.LegalView.as_view(), {"doc": "terminos"}, name="terms"),
    path("legal/privacidad/", views.LegalView.as_view(), {"doc": "privacidad"}, name="privacy"),
    path("legal/devoluciones/", views.LegalView.as_view(), {"doc": "devoluciones"}, name="refunds"),
    path(
        "legal/propiedad-intelectual/",
        views.LegalView.as_view(),
        {"doc": "propiedad-intelectual"},
        name="intellectual_property",
    ),
    # Rediseño 2026 — URLs retiradas, conservadas solo como redirect 301.
    path(
        "legal/devoluciones-y-reembolsos/",
        RedirectView.as_view(pattern_name="pages:refunds", permanent=True),
    ),
    path(
        "legal/nosotros/",
        RedirectView.as_view(pattern_name="pages:about", permanent=True),
    ),
]
