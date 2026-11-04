import hashlib
import hmac
import json
import logging
import math
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django_ratelimit.decorators import ratelimit

from cart.cart import Cart
from cart.suppliers import supplier_cart_context
from cart import mexico_geo
from cart.shipping import calc_shipping
from dropi_client import DropiClient, DropiAPIError

from catalog.inventory import get_available_stock, variant_stock_from_list
from catalog.warehouse_helpers import warehouse_id_from_raw
from catalog.models import Product
from catalog.store_config import store_config
from catalog.services.stock_sync import extract_stock, extract_variants

from .forms import (
    CheckoutForm,
    CITIES_BY_DEPARTMENT_CODE,
    department_code_for_city_name,
    state_code_for_department_name,
)
from .models import CheckoutAttempt, Order
from .whatsapp import customer_confirm_link
from .services import (
    create_order_with_carrier_fallback,
    fold_shipping_into_prices,
    extract_shipping_from_dropi,
    extract_tracking_from_webhook,
    notify_manual_dropi_order,
    notify_status_change,
    notify_supplier_out_of_stock,
    send_whatsapp_notification,
    sync_order_from_dropi,
    try_sync_order,
)

logger = logging.getLogger(__name__)


def _checkout_shipping_experiments(cart, city: str) -> list[dict]:
    """Bloque 'envío real + razón' por línea de carrito — SOLO para
    productos needs_combo (ver Product.needs_combo). Reutiliza el mismo
    contexto que la página de detalle para que el mensaje no se desincronice
    entre las dos pantallas."""
    from catalog.services.shipping_experiment import build_shipping_experiment_context

    experiments = []
    if not city:
        return experiments
    for item in cart:
        product = item.get("product")
        if not product or not product.needs_combo:
            continue
        experiments.append({
            "product": product,
            "item_name": item["name"],
            "experiment": build_shipping_experiment_context(product, city),
        })
    return experiments


# Segundos tras los que la marca "pedido en proceso" se da por vencida: si un
# error cortó la petición sin borrarla, el cliente no queda bloqueado viendo
# "Tu pedido ya se está procesando" en cada intento.
SUBMITTING_TTL_SECONDS = 90
_ATTEMPT_DATA_FIELDS = ("name", "surname", "phone", "email", "zip_code", "state", "city", "address", "notes")


def _record_checkout_attempt(request, stage, *, form=None, cart=None, errors=None, detail=""):
    """Guarda un intento de compra que no terminó en pedido (ver CheckoutAttempt).
    Nunca rompe el checkout: si falla, solo queda en el log."""
    try:
        if errors is None and form is not None:
            errors = {field: [str(e) for e in errs] for field, errs in form.errors.items()}
        data = {f: (request.POST.get(f) or "")[:500] for f in _ATTEMPT_DATA_FIELDS}
        items = [
            {"product_id": it.get("local_id"), "name": it.get("name"), "quantity": it.get("quantity"),
             "variation_id": it.get("variation_id")}
            for it in (cart.cart.values() if cart is not None else [])
        ]
        if not request.session.session_key:
            request.session.save()
        CheckoutAttempt.objects.create(
            session_key=request.session.session_key or "", stage=stage, errors=errors or {},
            data=data, cart=items, detail=detail[:4000],
        )
    except Exception:
        logger.exception("No se pudo guardar el intento de checkout fallido")


def _link_attempts_to_order(request, order) -> None:
    """Marca los intentos fallidos recientes del mismo visitante como recuperados."""
    key = request.session.session_key
    if not key:
        return
    try:
        CheckoutAttempt.objects.filter(
            session_key=key, order__isnull=True, created_at__gte=timezone.now() - timedelta(days=1),
        ).update(order=order)
    except Exception:
        logger.exception("No se pudo enlazar intentos fallidos al pedido #%s", order.pk)


def _checkout_page_context(request, cart, form, supplier_ctx):
    visitor_city = request.session.get("visitor_city")
    city_raw = form.data.get("city", "") if form.is_bound else form.initial.get("city", "")
    city_for_preview = ""
    if isinstance(visitor_city, dict):
        city_for_preview = visitor_city.get("city", "")
    if not city_for_preview:
        city_for_preview = city_raw
    return {
        "form": form,
        "cart": cart,
        "shipping_info": calc_shipping(list(cart.cart.values()), city_for_preview),
        "shipping_experiments": _checkout_shipping_experiments(cart, city_for_preview),
        "visitor_city": visitor_city,
        # Sin ciudad el cálculo cae en la zona C por defecto: la plantilla no
        # debe mostrar ese envío ni ese total como si fueran definitivos.
        "has_shipping_city": bool(city_for_preview),
        "city_display": city_raw,
        "cities_by_department_json": json.dumps(CITIES_BY_DEPARTMENT_CODE, ensure_ascii=False),
        **supplier_ctx,
    }


def checkout_summary_fragment(request):
    """Resumen del pedido re-renderizado con la ciudad guardada en sesión.

    El checkout lo pide tras elegir ciudad para refrescar envío y total sin
    recargar la página (recargar borraba lo que el cliente ya había escrito).
    A propósito no llama refresh_from_db ni log_shown: no debe duplicar
    mensajes flash ni inflar las métricas del experimento de envío.
    """
    from django.template.loader import render_to_string

    cart = Cart(request)
    if len(cart) == 0:
        return JsonResponse({"ok": False}, status=400)
    supplier_ctx = supplier_cart_context(cart.cart)
    context = _checkout_page_context(request, cart, CheckoutForm(), supplier_ctx)
    html = render_to_string("orders/partials/checkout_summary.html", context, request=request)
    return JsonResponse({"ok": True, "html": html})


@require_POST
@ratelimit(key="ip", rate="60/h", method="POST", block=True)
def checkout_attempt_log(request):
    """Registra un envío que el navegador frenó por datos incompletos (nunca
    llegó a checkout()): sin esto, quien se iba tras un error en el teléfono
    no dejaba rastro. Recibe los campos del formulario y `errors` en JSON."""
    try:
        errors = json.loads(request.POST.get("errors") or "{}")
        if not isinstance(errors, dict):
            errors = {}
    except ValueError:
        errors = {}
    errors = {str(k)[:40]: [str(v)[:300]] for k, v in list(errors.items())[:12]}
    _record_checkout_attempt(
        request, CheckoutAttempt.STAGE_VALIDATION, cart=Cart(request), errors=errors,
        detail=f"Frenado en el navegador antes de enviar (intento {request.POST.get('try', '?')} en esta visita)",
    )
    return JsonResponse({"ok": True})


@ratelimit(key='ip', rate='20/h', method='POST', block=True)
def checkout(request):
    cart = Cart(request)

    if len(cart) == 0:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("catalog:index")

    refresh_errors = cart.refresh_from_db()
    for msg in refresh_errors:
        messages.warning(request, msg)
    if len(cart) == 0:
        if request.method == "POST":
            _record_checkout_attempt(request, CheckoutAttempt.STAGE_UNAVAILABLE, errors={"__all__": refresh_errors})
        messages.error(request, "Tu carrito quedó vacío tras actualizar disponibilidad.")
        return redirect("catalog:index")

    supplier_ctx = supplier_cart_context(cart.cart)

    if request.method == "POST":
        submitting_since = request.session.get("checkout_submitting")
        try:
            submitting_recent = time.time() - float(submitting_since or 0) < SUBMITTING_TTL_SECONDS
        except (TypeError, ValueError):
            submitting_recent = False
        if submitting_recent:
            messages.warning(request, "Tu pedido ya se está procesando. Espera un momento.")
            return redirect("orders:checkout")

        form = CheckoutForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data

            # ── Validate stock and price from DB ─────────────────────────────
            # Un producto sin stock en SU proveedor asignado ya no bloquea el
            # checkout completo: se marca en unavailable_cart_keys y ese grupo
            # de proveedor se crea igual más abajo, pero sin enviarse a Dropi
            # (needs_manual_supplier=True) — Dropi puede tener el mismo
            # producto en otro proveedor que el equipo asigna a mano en vez de
            # perder la venta con un error en pantalla.
            unavailable_cart_keys: set[str] = set()
            for item in cart:
                product = item.get("product")
                if not product:
                    _record_checkout_attempt(request, CheckoutAttempt.STAGE_UNAVAILABLE, cart=cart,
                                             errors={"__all__": [f"Sin producto: {item.get('name')}"]})
                    messages.error(request, "Un producto del carrito ya no está disponible.")
                    return render(
                        request,
                        "orders/checkout.html",
                        _checkout_page_context(request, cart, form, supplier_ctx),
                    )
                vid = item.get("variation_id")
                item_stock = get_available_stock(product, vid)
                if item_stock <= 0 or item["quantity"] > item_stock:
                    unavailable_cart_keys.add(item["cart_key"])

            # ── Live re-check against Dropi (race-condition guard) ────────────
            # Local DB stock can be stale between sync runs; do one lightweight
            # check per distinct product (not the whole catalog) right before
            # creating the order, and self-heal the DB if Dropi's stock already
            # changed. Fired in parallel — sequential per-item HTTP calls here
            # used to add a full round-trip per distinct product to the
            # "Confirmar pedido" click, which is felt most on multi-item carts.
            cart_items = list(cart)
            unique_dropi_ids = {
                item["dropi_id"] for item in cart_items if item.get("product")
            }
            live_data_by_dropi_id: dict = {}
            if unique_dropi_ids:
                def _fetch_live_product(dropi_id):
                    try:
                        return dropi_id, DropiClient().get_product(dropi_id), None
                    except DropiAPIError as exc:
                        return dropi_id, None, exc

                with ThreadPoolExecutor(max_workers=min(8, len(unique_dropi_ids))) as executor:
                    for dropi_id, live_result, exc in executor.map(_fetch_live_product, unique_dropi_ids):
                        if exc is not None:
                            logger.warning(
                                "Live stock check failed for dropi_id=%s: %s — usando stock local.",
                                dropi_id, exc,
                            )
                            continue
                        live_data_by_dropi_id[dropi_id] = live_result

            live_suggested_price = {}
            live_warehouse_id = {}
            for item in cart_items:
                product = item.get("product")
                if not product:
                    continue
                live_data = live_data_by_dropi_id.get(item["dropi_id"])
                if live_data is None:
                    continue

                dropi_obj = live_data.get("objects") or live_data
                if isinstance(dropi_obj, list):
                    dropi_obj = dropi_obj[0] if dropi_obj else {}
                aggregate_live_stock = extract_stock(dropi_obj)

                suggested_raw = dropi_obj.get("suggested_price")
                try:
                    if suggested_raw:
                        live_suggested_price[item["dropi_id"]] = float(suggested_raw)
                except (TypeError, ValueError):
                    pass

                if aggregate_live_stock != product.stock:
                    # Sin last_synced: un cambio de stock no cambia la ficha
                    # (ver catalog.services.stock_sync.PAGE_FIELDS).
                    Product.objects.filter(pk=product.pk).update(stock=aggregate_live_stock)

                # Dropi's own order-creation endpoint validates the SPECIFIC
                # variation's warehouse stock, not the product aggregate — a
                # variant can be at zero while sibling variants keep the
                # aggregate positive. Check the exact variation here too, or
                # Dropi rejects the order after checkout instead of before it.
                variation_id = item.get("variation_id")
                if variation_id:
                    live_stock = variant_stock_from_list(
                        extract_variants(dropi_obj), variation_id, aggregate_live_stock
                    )
                else:
                    live_stock = aggregate_live_stock

                warehouse_id = warehouse_id_from_raw(dropi_obj, variation_id)
                live_warehouse_id[item["cart_key"]] = warehouse_id
                logger.info(
                    "Resolved warehouse_id=%s for dropi_id=%s variation_id=%s (live_stock=%s)",
                    warehouse_id, product.dropi_id, variation_id, live_stock,
                )

                if live_stock <= 0 or item["quantity"] > live_stock:
                    unavailable_cart_keys.add(item["cart_key"])

            request.session["checkout_submitting"] = time.time()
            group_token = uuid.uuid4()
            created_orders = []
            any_supplier_failed = False
            try:

                # ── Group cart items by supplier ──────────────────────────────────
                # Dropi does not support combining products from different
                # suppliers into a single order — a mixed order gets rejected with
                # a generic "Producto no posee stock en ninguna de sus bodegas"
                # even when every product genuinely has stock, because Dropi can
                # only resolve one supplier/warehouse per order. Each supplier
                # becomes its own local Order + Dropi order instead, sharing a
                # group_token so the confirmation page can show them together.
                supplier_groups: dict[int, list[dict]] = {}
                for item in cart:
                    supplier_groups.setdefault(int(item.get("supplier_id") or 0), []).append(item)

                visitor_city = request.session.get("visitor_city") or {}
                city_for_shipping = data.get("city") or visitor_city.get("city") or ""
                shipping_result = calc_shipping(list(cart.cart.values()), city_for_shipping)
                shipping_by_supplier = {
                    s["supplier_id"]: s["shipping_charged"] for s in shipping_result["supplier_breakdown"]
                }


                for supplier_id, group_items in supplier_groups.items():
                    # Dropi rejects orders where a product's unit price is below
                    # 80% of its own suggested_price ("El precio de venta no puede
                    # ser menor al 80%..."). Our local price can lag behind
                    # Dropi's live suggested price. Rather than surface that as a
                    # customer-facing error, bump the unit price sent to Dropi up
                    # to their floor and recover the difference via the shipping
                    # line, so the advertised product price never changes for the
                    # customer.
                    items_snapshot = []
                    dropi_products = []
                    price_shortfall = 0.0
                    for item in group_items:
                        items_snapshot.append(
                            {
                                "product_id": item.get("local_id"),
                                "dropi_id": item["dropi_id"],
                                "name": item["name"],
                                "quantity": item["quantity"],
                                "price": str(item["price"]),
                                "total": str(item["total_price"]),
                                "variation_id": item.get("variation_id"),
                            }
                        )
                        variation_id = item.get("variation_id")

                        unit_price = float(item["price"])
                        suggested = live_suggested_price.get(item["dropi_id"])
                        if suggested:
                            min_unit_price = math.ceil(suggested * 0.8) + 1
                            if unit_price < min_unit_price:
                                price_shortfall += (min_unit_price - unit_price) * item["quantity"]
                                unit_price = min_unit_price

                        dropi_item = {
                            "id": item["dropi_id"],
                            "user_id": item.get("supplier_id") or 0,
                            "name": item["name"],
                            "quantity": item["quantity"],
                            "price": unit_price,
                        }
                        if variation_id:
                            dropi_item["variation_id"] = variation_id
                        warehouse_id = live_warehouse_id.get(item["cart_key"])
                        if warehouse_id:
                            dropi_item["warehouse_id"] = warehouse_id
                        dropi_products.append(dropi_item)

                    products_subtotal = sum(item["total_price"] for item in group_items)
                    guide_cost = shipping_by_supplier.get(supplier_id, 0)
                    shipping_cost = int(guide_cost) + math.ceil(price_shortfall)
                    # Lo que paga el cliente = productos + el envío que vio en el
                    # checkout. total_order es lo que la transportadora cobra
                    # contra entrega: si no incluye el envío, ese envío se pierde
                    # (pasó con el pedido #92: se mostraron $80.000 y se cobraron
                    # $69.800).
                    total = float(products_subtotal) + shipping_cost
                    fold_shipping_into_prices(dropi_products, total)

                    group_unavailable_items = [
                        item for item in group_items if item["cart_key"] in unavailable_cart_keys
                    ]

                    # ── Create Order in Django FIRST to get the real PK ─────────
                    order = Order.objects.create(
                        user=None,
                        group_token=group_token,
                        dropi_order_id="",
                        name=data["name"],
                        surname=data["surname"],
                        email=data["email"],
                        phone=data["phone"],
                        address=data["address"],
                        city=data["city"],
                        state=data["state"],
                        zip_code=data.get("zip_code", ""),
                        notes=data.get("notes", ""),
                        payment_method=data["payment_method"],
                        total=products_subtotal,
                        shipping_cost=shipping_cost,
                        items=items_snapshot,
                        status=Order.STATUS_PENDING,
                        needs_manual_supplier=bool(group_unavailable_items),
                    )

                    if group_unavailable_items:
                        # El proveedor asignado no tiene stock de uno o más
                        # productos de este grupo — no tiene caso mandarlo a
                        # Dropi (lo rechazaría). Se deja el pedido creado como
                        # Pendiente de confirmación (su estado normal de todas
                        # formas) para que el equipo lo reasigne a otro proveedor
                        # a mano, y se avisa por WhatsApp al número de operaciones.
                        logger.warning(
                            "Order #%s (supplier=%s) sin stock en proveedor asignado: %s",
                            order.pk, supplier_id,
                            [it["name"] for it in group_unavailable_items],
                        )
                        try:
                            notify_supplier_out_of_stock(order, group_unavailable_items)
                        except Exception:
                            logger.exception("notify_supplier_out_of_stock failed for order #%s", order.pk)
                        created_orders.append(order)
                        continue

                    # ── Submit to Dropi with the real shop_order_id ─────────────
                    # Dropi México valida estado y ciudad contra su catálogo:
                    # se mandan sus nombres exactos, no los visibles.
                    dropi_state, dropi_city = mexico_geo.dropi_names(data["state"], data["city"])
                    dropi_payload = {
                        "total_order": total,
                        "notes": data.get("notes", ""),
                        "name": data["name"],
                        "surname": data["surname"],
                        "dir": data["address"],
                        "country": "MX",
                        "state": dropi_state,
                        "city": dropi_city,
                        "phone": data["phone"],
                        "client_email": data["email"],
                        "payment_method_id": 1,
                        "status": "PENDIENTE CONFIRMACION",
                        "type": "FINAL_ORDER",
                        "rate_type": data["payment_method"],
                        "products": dropi_products,
                        "calculate_costs_and_shiping": False,
                        "shop_order_id": order.pk,
                        "create_product_if_not_exist": False,
                        "zip_code": data.get("zip_code", ""),
                    }

                    try:
                        client = DropiClient()
                        logger.info("Submitting order #%s to Dropi (supplier=%s)", order.pk, supplier_id)
                        logger.info("Dropi payload products: %s", json.dumps(dropi_products, indent=2))

                        # Log local stock for debugging
                        for item in group_items:
                            product = item.get("product")
                            if product:
                                logger.info(
                                    "Product %s (dropi_id=%s): local_stock=%s, quantity=%s",
                                    product.name[:30],
                                    product.dropi_id,
                                    product.stock,
                                    item["quantity"]
                                )

                        resp = create_order_with_carrier_fallback(client, dropi_payload)
                        objects = resp.get("objects") or {}
                        dropi_order_id = str(
                            objects.get("id") or objects.get("order_id") or objects.get("orderId") or ""
                        )
                        # shipping_cost se queda con el envío que se le cobró al
                        # cliente: lo que devuelve Dropi es el costo de la guía
                        # para la tienda (o nada), no lo que paga el comprador.
                        dropi_guide_cost, _ = extract_shipping_from_dropi(objects)
                        order.dropi_order_id = dropi_order_id
                        order.total = products_subtotal + shipping_cost
                        order.save(update_fields=["dropi_order_id", "total"])
                        logger.info(
                            "Order #%s: cobrado al cliente %s (envío %s); guía según Dropi %s",
                            order.pk, order.total, shipping_cost, dropi_guide_cost,
                        )
                        logger.info("Order #%s created in Dropi as %s", order.pk, dropi_order_id)
                        created_orders.append(order)
                    except DropiAPIError as exc:
                        # El pedido NO se cancela: queda pendiente y marcado para
                        # crearlo a mano en Dropi (otra transportadora u otro
                        # proveedor). Antes se cancelaba y el cliente veía "intenta
                        # de nuevo", reintentaba varias veces y el equipo igual
                        # terminaba rehaciéndolo a mano.
                        logger.error(
                            "Dropi order failed for local order #%s (supplier=%s): %s",
                            order.pk, supplier_id, exc,
                        )
                        order.needs_manual_supplier = True
                        order.cancel_reason = f"Crear a mano en Dropi: {exc}"[:255]
                        order.save(update_fields=["needs_manual_supplier", "cancel_reason"])
                        try:
                            notify_manual_dropi_order(order, str(exc))
                        except Exception:
                            logger.exception("notify_manual_dropi_order failed for order #%s", order.pk)
                        created_orders.append(order)
                        any_supplier_failed = True

            except Exception:
                # Un error inesperado no puede dejar al cliente en una página
                # caída: se registra y, si ningún pedido alcanzó a crearse, se
                # vuelve al formulario con lo que escribió.
                logger.exception("Checkout falló con un error inesperado")
                _record_checkout_attempt(request, CheckoutAttempt.STAGE_ERROR, form=form, cart=cart,
                                         errors={"__all__": ["Error del sistema"]},
                                         detail=traceback.format_exc())
                if created_orders:
                    any_supplier_failed = True
            finally:
                request.session.pop("checkout_submitting", None)

            if not created_orders:
                messages.error(
                    request,
                    "No pudimos registrar tu pedido por un problema nuestro, no de tus datos. "
                    "Inténtalo de nuevo o escríbenos por WhatsApp y lo hacemos por ti.",
                )
                return render(
                    request,
                    "orders/checkout.html",
                    _checkout_page_context(request, cart, form, supplier_ctx),
                )

            # ── Send confirmation email(s) to customer ────────────────────────
            for created_order in created_orders:
                _send_order_confirmation_email(created_order)

            # ── Shipping-with-reason experiment (needs_combo products only) ──
            from catalog.services.shipping_experiment import log_purchase_outcome
            for created_order in created_orders:
                try:
                    log_purchase_outcome(created_order)
                except Exception:
                    logger.exception("log_purchase_outcome failed for order #%s", created_order.pk)

            if any_supplier_failed:
                messages.warning(
                    request,
                    "Recibimos tu pedido. Estamos programando el envío con la transportadora "
                    "y te escribimos por WhatsApp para confirmarlo.",
                )

            for created_order in created_orders:
                _link_attempts_to_order(request, created_order)

            cart.clear()
            # La confirmación dispara los eventos de compra una sola vez, en la
            # primera vista tras este checkout (ver order_confirmation).
            request.session["purchase_to_track"] = str(group_token)
            # Se muestra primero un pedido que sí entró a Dropi, si lo hay.
            primary = next((o for o in created_orders if not o.needs_manual_supplier), created_orders[0])
            return redirect("orders:confirmation", access_token=primary.access_token)
        _record_checkout_attempt(request, CheckoutAttempt.STAGE_VALIDATION, form=form, cart=cart)
    else:
        initial = {}
        visitor_city = request.session.get("visitor_city")
        if "city" not in initial and isinstance(visitor_city, dict):
            if visitor_city.get("city"):
                initial["city"] = visitor_city["city"]
        if not initial.get("state") and isinstance(visitor_city, dict):
            state_code = state_code_for_department_name(visitor_city.get("state", ""))
            if state_code:
                initial["state"] = state_code
        if not initial.get("state") and initial.get("city"):
            state_code = department_code_for_city_name(initial["city"])
            if state_code:
                initial["state"] = state_code
        form = CheckoutForm(initial=initial)

    checkout_context = _checkout_page_context(request, cart, form, supplier_ctx)

    if request.method == "GET":
        # Only log "shown" on a real page view — not on POST re-renders after
        # a validation error, which would inflate the count per retry.
        from catalog.services.shipping_experiment import log_shown

        if not request.session.session_key:
            request.session.save()
        for entry in checkout_context["shipping_experiments"]:
            log_shown(entry["product"], entry["experiment"], session_key=request.session.session_key or "")

    return render(request, "orders/checkout.html", checkout_context)


def order_confirmation(request, access_token):
    from urllib.parse import quote

    from django.conf import settings

    order = get_object_or_404(Order, access_token=access_token)
    try_sync_order(order)
    whatsapp = store_config()["whatsapp"]
    wa_message = f"Hola, quiero saber el estado de mi pedido #{order.pk}"
    # A cart with products from more than one supplier gets split into one
    # Dropi order per supplier (see checkout()) — show them together here so
    # the customer understands it's one purchase shipped in separate guides.
    sibling_orders = list(
        Order.objects.filter(group_token=order.group_token).exclude(pk=order.pk).order_by("pk")
    )
    for sibling in sibling_orders:
        try_sync_order(sibling)
    group_has_failed_order = order.status == Order.STATUS_CANCELLED or any(
        sib.status == Order.STATUS_CANCELLED for sib in sibling_orders
    )
    # Una compra = un checkout, aunque se haya dividido en varios pedidos por
    # proveedor. Se consume la marca de sesión para no volver a contarla.
    purchase_orders = [o for o in [order, *sibling_orders] if o.status != Order.STATUS_CANCELLED]
    track_purchase = bool(purchase_orders) and (
        request.session.get("purchase_to_track") == str(order.group_token)
    )
    if track_purchase:
        del request.session["purchase_to_track"]
    return render(request, "orders/confirmation.html", {
        "order": order,
        "sibling_orders": sibling_orders,
        "group_has_failed_order": group_has_failed_order,
        "can_cancel": order.can_cancel(),
        "cancel_deadline": order.cancel_deadline,
        "order_wa_track_href": f"https://wa.me/{whatsapp}?text={quote(wa_message)}",
        "customer_confirm_href": customer_confirm_link(order),
        "track_purchase": track_purchase,
        "purchase_total": sum((o.total for o in purchase_orders), Decimal("0")),
        "purchase_shipping": sum((o.shipping_cost or Decimal("0") for o in purchase_orders), Decimal("0")),
        "purchase_items": [item for o in purchase_orders for item in (o.items or [])],
    })


def order_detail(request, access_token):
    """Detailed order view — accessible by anyone holding the UUID token."""
    order = get_object_or_404(Order, access_token=access_token)
    try_sync_order(order)
    return render(request, "orders/detail.html", {
        "order": order,
        "can_cancel": order.can_cancel(),
        "cancel_deadline": order.cancel_deadline,
    })


@ratelimit(key="ip", rate="30/h", method="POST", block=True)
def order_review(request, access_token):
    """Opinar sobre los productos de un pedido entregado, sin cuenta: el
    enlace del pedido (UUID) es la credencial, igual que para verlo."""
    from django.core.exceptions import PermissionDenied, ValidationError

    from catalog.services.reviews import (
        order_can_be_reviewed,
        products_in_order,
        public_author_name,
        submit_order_review,
    )

    order = get_object_or_404(Order, access_token=access_token)
    products = products_in_order(order) if order_can_be_reviewed(order) else []
    existing = {r.product_id: r for r in order.reviews.all()} if products else {}

    if request.method == "POST" and products:
        saved = 0
        for product in products:
            raw = request.POST.get(f"score_{product.pk}", "")
            if not raw:
                continue
            try:
                submit_order_review(
                    order=order,
                    product=product,
                    score=int(raw),
                    comment=request.POST.get(f"comment_{product.pk}", ""),
                )
                saved += 1
            except (ValueError, ValidationError, PermissionDenied):
                continue
        if saved:
            messages.success(request, "¡Gracias por tu opinión! Ya está publicada en la tienda.")
            return redirect("orders:review", access_token=order.access_token)
        messages.error(request, "Elige de 1 a 5 estrellas en al menos un producto.")

    return render(request, "orders/review.html", {
        "order": order,
        "can_review": bool(products),
        "author_preview": ", ".join(
            part for part in (public_author_name(order.name, order.surname), (order.city or "").strip().title()) if part
        ),
        "rows": [{"product": p, "review": existing.get(p.pk)} for p in products],
    })


def order_cancel(request, access_token):
    order = get_object_or_404(Order, access_token=access_token)

    if request.method == "POST":
        if not order.can_cancel():
            messages.error(request, "El plazo de 15 minutos para cancelar ya expiró o el pedido no se puede cancelar.")
            return redirect("orders:confirmation", access_token=order.access_token)

        reason = request.POST.get("cancel_reason", "").strip()[:255]
        _perform_order_cancellation(order, reason)
        messages.success(request, "Tu pedido fue cancelado correctamente.")
        return redirect("orders:confirmation", access_token=order.access_token)

    return render(request, "orders/cancel.html", {
        "order": order,
        "can_cancel": order.can_cancel(),
        "cancel_deadline": order.cancel_deadline,
    })


# ── Helpers ───────────────────────────────────────────────────────────────────────────────────

def _send_order_confirmation_email(order: Order) -> None:
    """Send HTML confirmation email to customer. Fails silently on error."""
    if not order.email:
        return

    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from datetime import datetime

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@droppistore.co")
    subject = f"✅ Tu pedido #{order.pk} fue recibido — Pegasus Store"
    
    payment_label = "Contraentrega" if order.payment_method == "CON RECAUDO" else "Pago anticipado"
    site_url = getattr(settings, "STORE_SITE_URL", "").rstrip("/")
    logo_url = getattr(settings, "STORE_EMAIL_LOGO_URL", "")

    context = {
        "order": order,
        "payment_label": payment_label,
        "site_url": site_url,
        "logo_url": logo_url,
        "year": datetime.now().year,
        "store_whatsapp": store_config()["whatsapp"],
        "store_whatsapp_display": store_config()["whatsapp_display"],
    }
    
    # Plain text fallback
    items_lines = "\n".join(
        f"  • {it['name']} x{it['quantity']} — ${float(it['price']):,.0f}"
        for it in (order.items or [])
    )
    sep = "─" * 40
    text_body = (
        f"Hola {order.name},\n\n"
        f"¡Recibimos tu pedido correctamente! Aquí está el resumen:\n\n"
        f"Número de pedido: #{order.pk}\n"
        f"{sep}\n"
        f"{items_lines}\n"
        f"{sep}\n"
        f"Total: ${float(order.total):,.0f}\n"
        f"Envío a: {order.address}, {order.city} ({order.state})\n"
        f"Método de pago: {payment_label}\n\n"
        f"Recibirás tu pedido en 1 a 5 días hábiles después del despacho, según tu ciudad.\n\n"
        f"¡Gracias por tu compra!\n"
        f"— Equipo Pegasus Store"
    )

    try:
        html_body = render_to_string("emails/order_confirmation.html", context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[order.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
        
        logger.info("Confirmation email sent to %s for order #%s", order.email, order.pk)
    except Exception as exc:
        logger.error("Failed to send confirmation email for order #%s: %s", order.pk, exc)


# ── Webhook: Dropi → Django ────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def dropi_webhook(request):
    """
    Receives status-update notifications from Dropi.
    Expected JSON body: {"shop_order_id": <int>, "status": "<str>", ...}
    Optional HMAC verification via DROPI_WEBHOOK_SECRET setting.
    """
    # ── Optional signature verification ────────────────────────────────────
    webhook_secret = getattr(settings, "DROPI_WEBHOOK_SECRET", "")
    if webhook_secret:
        sig = request.headers.get("X-Dropi-Signature", "")
        expected = hmac.new(
            webhook_secret.encode(), request.body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return HttpResponse("Forbidden", status=403)

    # ── Parse body ──────────────────────────────────────────────────────────
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    shop_order_id = data.get("shop_order_id")
    if not shop_order_id:
        return JsonResponse({"ok": False, "error": "missing shop_order_id"}, status=400)

    # ── Find local order ────────────────────────────────────────────────────
    try:
        order = Order.objects.get(pk=shop_order_id)
    except Order.DoesNotExist:
        logger.warning("Dropi webhook: unknown shop_order_id=%s", shop_order_id)
        return JsonResponse({"ok": True})   # acknowledge silently

    # Unify webhook flow with Dropi sync service logic so status inference,
    # guide/tracking extraction and notifications are consistent everywhere.
    carrier, tracking_url = extract_tracking_from_webhook(data)
    if carrier and not data.get("shipping_company"):
        data["shipping_company"] = carrier
    if tracking_url and not data.get("tracking_url"):
        data["tracking_url"] = tracking_url

    changed, old_status = sync_order_from_dropi(order, data)
    if changed and order.status != old_status:
        notify_status_change(order, old_status)
        send_whatsapp_notification(order, old_status)
        logger.info("Order #%s status: %s → %s (webhook)", order.pk, old_status, order.status)

    return JsonResponse({"ok": True, "changed": changed})


# ── Seguimiento por número de guía o teléfono ──────────────────────────────────────────────────

@ratelimit(key='ip', rate='20/h', method='POST', block=True)
def track_order(request):
    """Búsqueda pública de pedido por número de guía o por teléfono (sin login).

    Coincidencia por guía: se comparan solo dígitos contra `shipping_guide`.
    Coincidencia por teléfono: 10 dígitos que empiecen por 3 → se muestra el
    pedido más reciente asociado a ese teléfono.
    """
    error = None
    if request.method == "POST":
        raw = (request.POST.get("guide") or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            error = "Escribe tu número de guía o el celular con el que pediste."
        else:
            candidates = Order.objects.filter(shipping_guide__isnull=False).exclude(shipping_guide="")
            match = None
            for candidate in candidates.order_by("-created_at")[:500]:
                if "".join(ch for ch in candidate.shipping_guide if ch.isdigit()) == digits:
                    match = candidate
                    break
            if not match and len(digits) == 10 and digits[0] == "3":
                match = (
                    Order.objects.filter(phone__endswith=digits[-10:])
                    .order_by("-created_at")
                    .first()
                )
            if match:
                try_sync_order(match)
                return redirect("orders:detail", access_token=match.access_token)
            error = "No encontramos ese número. Revísalo o escríbenos por WhatsApp."

    return render(request, "orders/track.html", {"error": error})


@require_GET
def order_status_api(request, access_token):
    """
    Lightweight JSON endpoint polled by the frontend every few seconds.
    Triggers a Dropi sync (respects 60-second cooldown) and returns
    the current order status so the browser can reload when it changes.
    """
    order = get_object_or_404(Order, access_token=access_token)
    try_sync_order(order)
    return JsonResponse({
        "status": order.status,
        "dropi_status": order.dropi_status or "",
        "shipping_guide": order.shipping_guide or "",
        "carrier": order.carrier or "",
        "tracking_url": order.tracking_url or "",
    })


def _perform_order_cancellation(order: Order, reason: str = "") -> None:
    pending_dropi = False
    if order.dropi_order_id:
        try:
            client = DropiClient()
            client.cancel_order(order.dropi_order_id, shop_order_id=order.pk)
        except DropiAPIError as exc:
            logger.warning(
                "Dropi cancel failed for order #%s (%s): %s — local cancel only",
                order.pk, order.dropi_order_id, exc,
            )
            pending_dropi = True

    order.status = Order.STATUS_CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason
    order.cancel_pending_dropi = pending_dropi
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "cancel_pending_dropi"])
    _send_cancellation_email(order, pending_dropi)


def _send_cancellation_email(order: Order, pending_dropi: bool) -> None:
    if not order.email:
        return
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@droppistore.co")
    subject = f"Pedido #{order.pk} cancelado — Pegasus Store"
    extra = (
        "\nEstamos procesando la cancelación en logística. Si ves algún cargo, contáctanos."
        if pending_dropi
        else ""
    )
    body = (
        f"Hola {order.name},\n\n"
        f"Confirmamos la cancelación de tu pedido #{order.pk}.{extra}\n\n"
        f"Total: ${float(order.total):,.0f}\n\n"
        f"— Equipo Pegasus Store"
    )
    try:
        send_mail(subject, body, from_email, [order.email], fail_silently=False)
    except Exception as exc:
        logger.error("Failed to send cancellation email for order #%s: %s", order.pk, exc)

