from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

from cart.cart import Cart

from orders.models import Order

from .dashboard_data import build_dashboard_context
from .forms import AvatarUploadForm, PostCheckoutSignupForm, StoreLoginForm, VoluntarySignupForm
from .models import CustomerProfile
from .services import link_orders_to_user


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True), name='post')
class StoreLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = StoreLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        link_orders_to_user(self.request.user)
        messages.success(self.request, "Sesión iniciada correctamente.")
        return response


@login_required
def dashboard(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")[:5]
    cart = Cart(request)
    ctx = build_dashboard_context(request.user, request)
    ctx["orders"] = orders
    ctx["user"] = request.user
    ctx["cart_count"] = len(cart)
    ctx["cart_total"] = cart.get_total()
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    ctx["profile"] = profile
    ctx["avatar_form"] = AvatarUploadForm()
    return render(request, "accounts/dashboard.html", ctx)


@login_required
@require_POST
def update_avatar(request):
    form = AvatarUploadForm(request.POST, request.FILES)
    if form.is_valid():
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        if profile.avatar:
            profile.avatar.delete(save=False)
        profile.avatar = form.cleaned_data["avatar"]
        profile.save(update_fields=["avatar"])
        messages.success(request, "Foto de perfil actualizada.")
    else:
        messages.error(request, "Archivo inválido. Sube una imagen (JPG, PNG, WebP).")
    return redirect("accounts:dashboard")


@login_required
def my_reviews(request):
    from catalog.services import get_dashboard_review_data
    pending, my_review_list = get_dashboard_review_data(request.user, limit=50)
    return render(request, "accounts/my_reviews.html", {
        "pending_reviews": pending,
        "my_reviews": my_review_list,
        "user": request.user,
    })


def signup_after_order(request, access_token):
    order = get_object_or_404(Order, access_token=access_token)
    if request.user.is_authenticated:
        link_orders_to_user(request.user, order.email)
        order.user = request.user
        order.save(update_fields=["user"])
        return redirect("orders:my_orders")

    if request.method == "POST":
        if getattr(request, 'limited', False):
            messages.error(request, "Demasiados intentos. Intenta de nuevo más tarde.")
            return redirect(request.path)
        form = PostCheckoutSignupForm(request.POST, order_email=order.email)
        if form.is_valid():
            user = form.save()
            CustomerProfile.objects.get_or_create(user=user)
            link_orders_to_user(user, order.email)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Cuenta creada. Tus pedidos quedaron vinculados.")
            return redirect("orders:my_orders")
    else:
        form = PostCheckoutSignupForm(order_email=order.email)

    return render(request, "accounts/signup_after_order.html", {
        "form": form,
        "order": order,
    })


@ratelimit(key='ip', rate='5/h', method='POST', block=True)
def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = VoluntarySignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            CustomerProfile.objects.get_or_create(user=user)
            link_orders_to_user(user, user.email)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, f"¡Bienvenido/a, {user.first_name}! Tu cuenta fue creada.")
            return redirect("accounts:dashboard")
    else:
        form = VoluntarySignupForm()

    return render(request, "accounts/signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Sesión cerrada.")
    return redirect("catalog:index")
