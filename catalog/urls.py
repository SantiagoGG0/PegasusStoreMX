from django.urls import path
from . import feeds, views

app_name = "catalog"

urlpatterns = [
    path("", views.catalog_index, name="index"),
    path("categoria/<slug:slug>/", views.catalog_category, name="category"),
    path("categoria/<slug:category_slug>/<slug:slug>/", views.collection_detail, name="collection"),
    path("producto/<slug:slug>/", views.product_detail, name="detail"),
    path("productos/fragmento/", views.catalog_products_fragment, name="products_fragment"),
    path("pdp-productos/<int:exclude_pk>/fragmento/", views.pdp_more_products, name="pdp_more_products"),
    path("buscar/sugerencias/", views.search_suggestions, name="search_suggestions"),
    path("feeds/google-merchant.xml", feeds.google_merchant_feed, name="google_merchant_feed"),
]
