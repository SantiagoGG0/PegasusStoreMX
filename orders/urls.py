from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/resumen/", views.checkout_summary_fragment, name="checkout_summary"),
    path("checkout/intento/", views.checkout_attempt_log, name="checkout_attempt"),
    path("confirmacion/<uuid:access_token>/", views.order_confirmation, name="confirmation"),
    path("detalle/<uuid:access_token>/", views.order_detail, name="detail"),
    path("cancelar/<uuid:access_token>/", views.order_cancel, name="cancel"),
    path("opinar/<uuid:access_token>/", views.order_review, name="review"),
    path("seguimiento/", views.track_order, name="track"),
    path("webhook/dropi/", views.dropi_webhook, name="dropi_webhook"),
    path("api/estado/<uuid:access_token>/", views.order_status_api, name="order_status_api"),
]
