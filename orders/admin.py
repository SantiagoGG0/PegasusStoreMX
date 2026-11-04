from django.contrib import admin
from django.contrib import messages
from django.urls import reverse
from django.utils.html import format_html, mark_safe

from .models import CheckoutAttempt, Order

_WA_BTN_STYLE = (
    "display:inline-block;padding:6px 12px;border-radius:999px;background:#1FA855;"
    "color:#fff;font-weight:700;white-space:nowrap;text-decoration:none"
)
_WA_BTN_STYLE_SECONDARY = (
    "display:inline-block;padding:6px 12px;border-radius:999px;border:1px solid #1FA855;"
    "color:#178F47;font-weight:700;white-space:nowrap;text-decoration:none"
)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "full_name", "email", "phone",
        "city_state", "payment_method",
        "total_display", "status_badge", "supplier_flag",
        "dropi_order_id", "cancel_pending_dropi",
        "created_at", "whatsapp_next",
    )
    list_filter = (
        "status", "needs_manual_supplier", "payment_method", "state",
        "cancel_pending_dropi", "created_at",
    )
    search_fields = ("name", "surname", "email", "phone", "dropi_order_id")
    readonly_fields = (
        "access_token", "dropi_order_id", "created_at", "total",
        "items_display", "confirmation_link", "cancelled_at", "whatsapp_actions",
    )
    actions = [
        "mark_cancelled", "send_confirmation_email", "send_status_notification",
        "mark_supplier_resolved",
    ]
    fieldsets = (
        ("WhatsApp (gratis: abre tu WhatsApp con el mensaje escrito)", {
            "fields": ("whatsapp_actions",),
        }),
        ("Cliente", {
            "fields": ("user", "name", "surname", "email", "phone"),
        }),
        ("Envío", {
            "fields": ("address", "colonia", "city", "state", "zip_code", "notes"),
        }),
        ("Pedido", {
            "fields": (
                "payment_method", "total", "status",
                "dropi_order_id", "items_display", "created_at",
                "needs_manual_supplier",
                "cancelled_at", "cancel_reason", "cancel_pending_dropi",
            ),
        }),
        ("Acceso seguro", {
            "fields": ("access_token", "confirmation_link"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Cliente", ordering="name")
    def full_name(self, obj):
        return f"{obj.name} {obj.surname}"

    @admin.display(description="Ciudad / Dpto")
    def city_state(self, obj):
        return f"{obj.city} / {obj.state}"

    @admin.display(description="Total", ordering="total")
    def total_display(self, obj):
        return mark_safe(f"${float(obj.total):,.0f}")

    @admin.display(description="Estado", ordering="status")
    def status_badge(self, obj):
        return obj.get_status_display()

    @admin.display(description="Proveedor", ordering="needs_manual_supplier")
    def supplier_flag(self, obj):
        if not obj.needs_manual_supplier:
            return "—"
        # cancel_reason guarda lo que respondió Dropi (ciudad sin cobertura,
        # producto archivado…) o queda vacío si fue falta de stock.
        detail = (obj.cancel_reason or "Proveedor sin stock").replace("Crear a mano en Dropi: ", "")
        return format_html(
            '<span style="color:#b91c1c;font-weight:700">⚠️ Crear a mano en Dropi</span>'
            '<br><small style="color:#7f1d1d">{}</small>',
            detail[:140],
        )

    @admin.display(description="WhatsApp")
    def whatsapp_next(self, obj):
        """El mensaje que toca según el estado (guía, reseña o confirmar)."""
        from .whatsapp import admin_actions

        primary = next((a for a in admin_actions(None, obj) if a["primary"]), None)
        if not primary:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" style="{}">{}</a>',
            primary["href"], _WA_BTN_STYLE, primary["label"],
        )

    @admin.display(description="Mensajes")
    def whatsapp_actions(self, obj):
        from django.utils.html import format_html_join

        from .whatsapp import admin_actions

        actions = admin_actions(None, obj) if obj and obj.pk else []
        if not actions:
            return "Sin celular válido para WhatsApp."
        return format_html(
            '<div style="display:flex;flex-wrap:wrap;gap:8px">{}</div>'
            '<p style="margin:8px 0 0;color:#666">Se abre WhatsApp con el texto listo; revísalo y pulsa enviar.</p>',
            format_html_join(
                "",
                '<a href="{}" target="_blank" rel="noopener" style="{}">{}</a>',
                ((a["href"], _WA_BTN_STYLE if a["primary"] else _WA_BTN_STYLE_SECONDARY, a["label"]) for a in actions),
            ),
        )

    @admin.display(description="Confirmación")
    def confirmation_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("orders:confirmation", kwargs={"access_token": obj.access_token})
        return format_html('<a href="{}" target="_blank">Ver página</a>', url)

    @admin.display(description="Ítems del pedido")
    def items_display(self, obj):
        if not obj.items:
            return "—"
        rows = "".join(
            f"<tr><td style='padding:4px 8px'>{it.get('name','')}</td>"
            f"<td style='padding:4px 8px;text-align:center'>{it.get('quantity',1)}</td>"
            f"<td style='padding:4px 8px;text-align:right'>${float(it.get('price',0)):,.0f}</td></tr>"
            for it in obj.items
        )
        return format_html(
            "<table style='border-collapse:collapse;font-size:13px'>"
            "<thead><tr><th style='padding:4px 8px;text-align:left'>Producto</th>"
            "<th style='padding:4px 8px'>Cant.</th>"
            "<th style='padding:4px 8px'>Precio</th></tr></thead>"
            "<tbody>{}</tbody></table>",
            format_html(rows),
        )

    @admin.action(description="Marcar como cancelado")
    def mark_cancelled(self, request, queryset):
        updated = queryset.exclude(status=Order.STATUS_CANCELLED).update(
            status=Order.STATUS_CANCELLED,
        )
        self.message_user(request, f"{updated} pedido(s) marcados como cancelados.")

    @admin.action(description="📧 Enviar email de confirmación")
    def send_confirmation_email(self, request, queryset):
        from orders.views import _send_order_confirmation_email
        
        success = 0
        failed = 0
        for order in queryset:
            try:
                _send_order_confirmation_email(order)
                success += 1
            except Exception as e:
                failed += 1
        
        if success:
            messages.success(request, f"✅ {success} email(s) de confirmación enviados.")
        if failed:
            messages.error(request, f"❌ {failed} email(s) fallaron.")

    @admin.action(description="📬 Enviar notificación de estado actual")
    def send_status_notification(self, request, queryset):
        from orders.services import notify_status_change
        
        success = 0
        failed = 0
        for order in queryset:
            try:
                # Send notification with fake old status to trigger email
                notify_status_change(order, "")
                success += 1
            except Exception as e:
                failed += 1
        
        if success:
            messages.success(request, f"✅ {success} notificación(es) de estado enviadas.")
        if failed:
            messages.error(request, f"❌ {failed} notificación(es) fallaron.")

    @admin.action(description="✅ Marcar proveedor ya reasignado")
    def mark_supplier_resolved(self, request, queryset):
        updated = queryset.filter(needs_manual_supplier=True).update(needs_manual_supplier=False)
        self.message_user(request, f"{updated} pedido(s) marcados como resueltos.")

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj:
            ro += ["name", "surname", "email", "phone",
                   "address", "colonia", "city", "state", "zip_code", "notes",
                   "payment_method", "total"]
        return ro

    ordering = ("-created_at",)


@admin.register(CheckoutAttempt)
class CheckoutAttemptAdmin(admin.ModelAdmin):
    """Envíos del formulario de compra que no terminaron en pedido: qué campo
    falló, con qué mensaje, y un botón para escribirle al cliente."""

    list_display = ("created_at", "stage", "customer", "city_state", "failed_fields", "products", "recovered",
                    "whatsapp")
    list_filter = ("stage", "created_at")
    search_fields = ("data__phone", "data__name", "data__city")
    readonly_fields = ("created_at", "stage", "errors_display", "data_display", "cart", "order", "session_key",
                       "detail", "whatsapp")
    exclude = ("errors", "data")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    @admin.display(description="Cliente")
    def customer(self, obj):
        d = obj.data or {}
        return f"{d.get('name', '')} {d.get('surname', '')}".strip() or "—"

    @admin.display(description="Ciudad")
    def city_state(self, obj):
        d = obj.data or {}
        return " · ".join(x for x in (d.get("city"), d.get("state")) if x) or "—"

    @admin.display(description="Qué falló")
    def failed_fields(self, obj):
        labels = {"name": "Nombre", "surname": "Apellido", "phone": "Teléfono", "email": "Correo",
                  "zip_code": "Código postal", "state": "Estado", "city": "Municipio", "address": "Calle y número",
                  "colonia": "Colonia", "notes": "Indicaciones",
                  "__all__": "General"}
        return ", ".join(labels.get(f, f) for f in (obj.errors or {})) or "—"

    @admin.display(description="Productos")
    def products(self, obj):
        return ", ".join(f"{it.get('name')} x{it.get('quantity')}" for it in (obj.cart or []))[:120] or "—"

    @admin.display(description="¿Compró después?", boolean=True)
    def recovered(self, obj):
        return obj.order_id is not None

    @admin.display(description="Mensajes que vio el cliente")
    def errors_display(self, obj):
        rows = "".join(
            format_html("<li><strong>{}</strong>: {}</li>", field, " / ".join(msgs))
            for field, msgs in (obj.errors or {}).items()
        )
        return mark_safe(f"<ul>{rows}</ul>") if rows else "—"

    @admin.display(description="Lo que escribió")
    def data_display(self, obj):
        rows = "".join(format_html("<li><strong>{}</strong>: {}</li>", k, v) for k, v in (obj.data or {}).items() if v)
        return mark_safe(f"<ul>{rows}</ul>") if rows else "—"

    @admin.display(description="WhatsApp")
    def whatsapp(self, obj):
        from .whatsapp import customer_wa_number, wa_link

        d = obj.data or {}
        number = customer_wa_number(d.get("phone", ""))
        if not number or obj.order_id:
            return "—"
        first = (d.get("name") or "").strip().split(" ")[0].title()
        items = ", ".join(it.get("name") or "" for it in (obj.cart or []))
        text = (f"Hola {first}, te escribimos de Pegasus Store. Vimos que intentaste pedir {items} y no se "
                "completó. ¿Te ayudamos a terminar el pedido por aquí?")
        return format_html('<a href="{}" target="_blank" rel="noopener" style="{}">Escribir</a>',
                           wa_link(number, text), _WA_BTN_STYLE)
