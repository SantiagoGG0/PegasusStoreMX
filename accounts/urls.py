from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("entrar/", views.StoreLoginView.as_view(), name="login"),
    path("registrarse/", views.signup, name="signup"),
    path("salir/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("avatar/", views.update_avatar, name="update_avatar"),
    path("mis-resenas/", views.my_reviews, name="my_reviews"),
    path(
        "registro-pedido/<uuid:access_token>/",
        views.signup_after_order,
        name="signup_after_order",
    ),
]
