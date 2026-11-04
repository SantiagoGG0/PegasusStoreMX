from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from catalog.models import Product

from .cart import Cart
from .recommendations import products_for_cart
from .shipping import shipping_from_session
from .suppliers import supplier_cart_context, supplier_shipping_groups


_SUGGESTED_PAGE_SIZE = 12


def _wants_json(request) -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _build_cart_items(cart: Cart) -> list[dict]:
    items = []
    for line in cart:
        product = line.get("product")
        if not product:
            continue
        variation_label = line.get("variation_label") or ""
        items.append({
            "cart_key": line["cart_key"],
            "product": product,
            "quantity": line["quantity"],
            "unit_price": line["price"],
            "subtotal": line["total_price"],
            "variation_label": variation_label,
            "max_stock": line.get("stock") or product.stock,
            "supplier_id": int(line.get("supplier_id") or product.supplier_id or 0),
        })
    return items


def _cart_state_payload(
    request,
    cart: Cart,
    *,
    warning: str = "",
    error: str = "",
) -> dict:
    items = _build_cart_items(cart)
    item_count = sum(i["quantity"] for i in items)
    supplier_ctx = supplier_cart_context(cart.cart)
    visitor_city = request.session.get("visitor_city")
    shipping_info = shipping_from_session(cart, visitor_city)
    shipping_groups = supplier_shipping_groups(items, _known_city_shipping(visitor_city, shipping_info))
    notice_html = render_to_string(
        "cart/partials/supplier_notice.html",
        {
            "multi_supplier": supplier_ctx["multi_supplier"],
            "supplier_count": supplier_ctx["supplier_count"],
            "item_count": item_count,
        },
    )
    shipping_html = render_to_string(
        "cart/partials/shipping_summary.html",
        {"shipping_groups": shipping_groups},
    )
    summary_totals_html = render_to_string(
        "cart/partials/summary_panel.html",
        {
            "cart_items": items,
            "item_count": item_count,
            "total": cart.get_total() if items else 0,
            "shipping_groups": shipping_groups,
            "shipping_info": shipping_info,
            "visitor_city": visitor_city,
        },
        request=request,
    )
    return {
        "success": not error,
        "error": error,
        "warning": warning,
        "empty": len(items) == 0,
        "cart_count": len(cart),
        "item_count": item_count,
        "total": str(cart.get_total()) if items else "0",
        "multi_supplier": supplier_ctx["multi_supplier"],
        "supplier_count": supplier_ctx["supplier_count"],
        "notice_html": notice_html,
        "shipping_groups_html": shipping_html,
        "summary_totals_html": summary_totals_html,
        "lines": [
            {
                "cart_key": i["cart_key"],
                "quantity": i["quantity"],
                "subtotal": str(i["subtotal"]),
                "unit_price": str(i["unit_price"]),
                "max_stock": i["max_stock"],
                "product_name": i["product"].name,
                "product_slug": i["product"].slug,
                "product_image": i["product"].display_main_image,
                "variation_label": i.get("variation_label") or "",
                "supplier_id": i["supplier_id"],
                "free_shipping": bool(i["product"].likely_free_shipping),
            }
            for i in items
        ],
    }


def _json_or_redirect(request, cart: Cart, *, warning: str = "", error: str = ""):
    if _wants_json(request):
        status = 400 if error else 200
        return JsonResponse(_cart_state_payload(request, cart, warning=warning, error=error), status=status)
    if error:
        messages.error(request, error)
    elif warning:
        messages.warning(request, warning)
    return redirect("cart:detail")


def _suggested_page(cart: Cart, page_num: int = 1):
    suggested_products, priority_supplier_id = products_for_cart(cart)
    paginator = Paginator(suggested_products, _SUGGESTED_PAGE_SIZE)
    return paginator.get_page(page_num), priority_supplier_id


def _known_city_shipping(visitor_city, shipping_info):
    """El cálculo de envío solo vale si el cliente ya eligió ciudad; sin ella
    calc_shipping usa la zona C por defecto, que no es su envío."""
    return shipping_info if (visitor_city or {}).get("city") else None


def _cart_shipping_groups(request, cart, cart_items):
    visitor_city = request.session.get("visitor_city")
    if not (visitor_city or {}).get("city"):
        return supplier_shipping_groups(cart_items)
    return supplier_shipping_groups(cart_items, shipping_from_session(cart, visitor_city))


def _cart_detail_context(request, cart=None):
    cart = cart or Cart(request)
    cart_items = _build_cart_items(cart)
    suggested_page_obj, priority_supplier_id = _suggested_page(cart)
    item_count = sum(i["quantity"] for i in cart_items)
    return {
        "cart": cart,
        "cart_items": cart_items,
        "total": cart.get_total(),
        "item_count": item_count,
        "suggested_products": suggested_page_obj.object_list,
        "suggested_page_obj": suggested_page_obj,
        "priority_supplier_id": priority_supplier_id,
        "shipping_groups": _cart_shipping_groups(request, cart, cart_items),
        **supplier_cart_context(cart.cart),
    }


def cart_detail(request):
    return render(request, "cart/detail.html", _cart_detail_context(request))


@require_GET
@ensure_csrf_cookie
def cart_state(request):
    """Read-only JSON snapshot of the cart, used to populate the cart drawer on open.
    También entrega la cookie de seguridad (CSRF): las páginas del catálogo se
    sirven desde caché sin cookies y window.pgsCsrf() la pide aquí antes de
    agregar al carrito o comprar."""
    cart = Cart(request)
    return JsonResponse(_cart_state_payload(request, cart))


@require_GET
def cart_content_fragment(request):
    if not _wants_json(request):
        return redirect("cart:detail")
    ctx = _cart_detail_context(request)
    html = render_to_string("cart/partials/cart_body.html", ctx, request=request)
    return JsonResponse({
        "html": html,
        "empty": len(ctx["cart_items"]) == 0,
        "cart_count": len(ctx["cart"]),
    })


@require_GET
def cart_suggested_products_fragment(request):
    cart = Cart(request)
    try:
        page_num = int(request.GET.get("page", 2))
    except (TypeError, ValueError):
        page_num = 2

    page_obj, _priority_supplier_id = _suggested_page(cart, page_num)
    html = "".join(
        render_to_string(
            "catalog/partials/product_card.html",
            {"product": product, "catalog_fragment": True},
            request=request,
        )
        for product in page_obj
    )
    loaded_count = page_obj.end_index() if page_obj.object_list else 0
    return JsonResponse({
        "html": html,
        "has_next": page_obj.has_next(),
        "page": page_obj.number,
        "loaded_count": loaded_count,
        "total_count": page_obj.paginator.count,
    })


@require_GET
def cart_buy_now(request, product_id):
    """Shareable link: add product to cart and go to checkout."""
    cart = Cart(request)
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    try:
        quantity = max(1, min(int(request.GET.get("qty", 1)), 99))
    except (TypeError, ValueError):
        quantity = 1
    variation_id_raw = request.GET.get("variation_id")
    variation_id = int(variation_id_raw) if variation_id_raw and str(variation_id_raw).isdigit() else None
    ok, err, warn = cart.add(product=product, quantity=quantity, variation_id=variation_id)
    if not ok:
        messages.error(request, err)
        return redirect(product.get_absolute_url())
    if warn:
        messages.warning(request, warn)
    return redirect("orders:checkout")


@require_POST
def cart_add_quick(request, product_id):
    """AJAX-only quick-add used by product card buttons. Returns JSON."""
    cart = Cart(request)
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    quantity = int(request.POST.get("quantity", 1))
    variation_id_raw = request.POST.get("variation_id")
    variation_id = int(variation_id_raw) if variation_id_raw and variation_id_raw.isdigit() else None
    ok, err, warn = cart.add(product=product, quantity=quantity, variation_id=variation_id)
    payload = _cart_state_payload(request, cart, warning=warn, error=(err if not ok else ""))
    payload.update(supplier_cart_context(cart.cart))
    if ok:
        payload["added_product"] = {
            "id": str(product.pk),
            "name": product.name,
            "price": float(product.price),
            "quantity": quantity,
        }
    status = 400 if not ok else 200
    return JsonResponse(payload, status=status)


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    quantity = int(request.POST.get("quantity", 1))
    override = request.POST.get("override") == "true"
    variation_id_raw = request.POST.get("variation_id")
    variation_id = int(variation_id_raw) if variation_id_raw and variation_id_raw.isdigit() else None
    ok, err, warn = cart.add(
        product=product,
        quantity=quantity,
        override_qty=override,
        variation_id=variation_id,
    )
    if not ok:
        if _wants_json(request):
            return JsonResponse(
                {"success": False, "error": err, "cart_count": len(cart), **supplier_cart_context(cart.cart)},
                status=400,
            )
        messages.error(request, err)
        return redirect(product.get_absolute_url())
    if warn:
        messages.warning(request, warn)
    if _wants_json(request):
        payload = _cart_state_payload(request, cart, warning=warn)
        payload["success"] = True
        payload.update(supplier_cart_context(cart.cart))
        return JsonResponse(payload)
    next_url = request.POST.get("next")
    if next_url == "checkout":
        return redirect("orders:checkout")
    return redirect("cart:detail")


@require_POST
def cart_update(request):
    cart = Cart(request)
    cart_key = request.POST.get("cart_key", "").strip()
    if not cart_key or cart_key not in cart.cart:
        return _json_or_redirect(
            request, cart, error="No se encontró el producto en el carrito."
        )

    line = cart.get_line(cart_key)
    product = get_object_or_404(Product, pk=line.get("local_id") or int(cart_key.split("_")[0]))

    action = request.POST.get("action", "")
    current_qty = line["quantity"]
    if action == "increment":
        quantity = current_qty + 1
    elif action == "decrement":
        quantity = current_qty - 1
    else:
        try:
            quantity = int(request.POST.get("quantity", current_qty))
        except (TypeError, ValueError):
            quantity = current_qty

    from catalog.inventory import get_available_stock

    max_stock = get_available_stock(product, line.get("variation_id"))
    line["stock"] = max_stock
    warning = ""
    if quantity > max_stock:
        warning = f"Solo hay {max_stock} unidades disponibles de «{product.name}»."
        quantity = max_stock

    if quantity < 1:
        cart.remove(cart_key=cart_key)
    else:
        cart.update_quantity(cart_key, quantity)

    return _json_or_redirect(request, cart, warning=warning)


@require_POST
def cart_remove(request, product_id=None):
    cart = Cart(request)
    cart_key = request.POST.get("cart_key", "").strip()
    if cart_key:
        cart.remove(cart_key=cart_key)
    else:
        product = get_object_or_404(Product, pk=product_id)
        variation_id_raw = request.POST.get("variation_id")
        variation_id = int(variation_id_raw) if variation_id_raw and variation_id_raw.isdigit() else None
        cart.remove(product=product, variation_id=variation_id)
    return _json_or_redirect(request, cart)


@require_GET
@cache_control(public=True, max_age=86400)
def cities_json(request):
    """Municipios con contra entrega como [[municipio, estado], …] para el
    buscador de ciudad de la ficha. Va aparte (y cacheado) para no meter
    cientos de <option> en el HTML de cada ficha."""
    from .mexico_geo import municipios_by_state_label

    rows = sorted(
        ([city, state] for state, cities in municipios_by_state_label().items() for city in cities),
        key=lambda row: (row[0], row[1]),
    )
    return JsonResponse({"cities": rows})


@require_GET
@cache_control(public=True, max_age=86400)
def zip_lookup(request, zip_code):
    """CP → [{state, state_label, city}] para llenar estado y municipio en el
    checkout. Lista vacía = CP sin datos en Dropi (el cliente elige a mano)."""
    from .mexico_geo import lookup_zip, state_label

    matches = [
        {"state": code, "state_label": state_label(code), "city": city}
        for code, city in lookup_zip(zip_code)
    ]
    return JsonResponse({"zip": zip_code, "matches": matches})


@require_POST
def save_city(request):
    """Save buyer city to session for shipping calculations."""
    from .shipping import get_zone

    city = request.POST.get("city", "").strip()
    state = request.POST.get("state", "").strip()

    if not city:
        return JsonResponse({"ok": False, "error": "Ciudad requerida"}, status=400)

    zone_info = get_zone(city)
    request.session["visitor_city"] = {
        "city": city,
        "state": state,
        "zone": zone_info["zone"],
        "guide_cost": zone_info["guide_cost"],
    }
    return JsonResponse({
        "ok": True,
        "zone": zone_info["zone"],
        "guide_cost": zone_info["guide_cost"],
    })
