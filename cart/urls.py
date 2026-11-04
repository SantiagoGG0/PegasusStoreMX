from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("contenido/", views.cart_content_fragment, name="content_fragment"),
    path("estado/", views.cart_state, name="state"),
    path("sugeridos/fragmento/", views.cart_suggested_products_fragment, name="suggested_fragment"),
    path("comprar/<int:product_id>/", views.cart_buy_now, name="buy_now"),
    path("agregar/<int:product_id>/", views.cart_add, name="add"),
    path("agregar-rapido/<int:product_id>/", views.cart_add_quick, name="add_quick"),
    path("actualizar/", views.cart_update, name="update"),
    path("eliminar/", views.cart_remove, name="remove"),
    path("eliminar/<int:product_id>/", views.cart_remove, name="remove_legacy"),
    path("ciudad/", views.save_city, name="save_city"),
    path("ciudades.json", views.cities_json, name="cities_json"),
    path("cp/<str:zip_code>.json", views.zip_lookup, name="zip_lookup"),
]
