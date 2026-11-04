import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    PAYMENT_COD = "CON RECAUDO"
    PAYMENT_PREPAID = "SIN RECAUDO"
    PAYMENT_CHOICES = [
        (PAYMENT_COD, "Pago contra entrega"),
        (PAYMENT_PREPAID, "Pago anticipado"),
    ]

    STATUS_PENDING = "PENDIENTE CONFIRMACION"
    STATUS_CONFIRMED = "CONFIRMADO"
    STATUS_SENT = "ENVIADO"
    STATUS_DELIVERED = "ENTREGADO"
    STATUS_CANCELLED = "CANCELADO"

    CANCEL_WINDOW_MINUTES = 15

    access_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    group_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        verbose_name="Grupo de pedido",
        help_text="Compartido entre las órdenes generadas por un mismo checkout "
        "(un pedido con productos de varias bodegas se divide en una orden Dropi "
        "por bodega, ya que Dropi no admite mezclarlas en una sola).",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        verbose_name="Cuenta",
    )

    dropi_order_id = models.CharField(
        max_length=100, blank=True, verbose_name="ID orden Dropi"
    )

    name = models.CharField(max_length=200, verbose_name="Nombre")
    surname = models.CharField(max_length=200, verbose_name="Apellido")
    email = models.EmailField(verbose_name="Correo electrónico")
    phone = models.CharField(max_length=30, verbose_name="Teléfono")
    address = models.CharField(max_length=500, verbose_name="Dirección")
    city = models.CharField(max_length=200, verbose_name="Ciudad")
    state = models.CharField(max_length=200, verbose_name="Departamento")
    zip_code = models.CharField(max_length=20, blank=True, verbose_name="Código postal")
    notes = models.TextField(blank=True, verbose_name="Notas del pedido")

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default=PAYMENT_COD,
        verbose_name="Método de pago",
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Total")
    shipping_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Costo de envío",
    )
    status = models.CharField(
        max_length=50, default=STATUS_PENDING, verbose_name="Estado"
    )
    items = models.JSONField(default=list, verbose_name="Ítems del pedido")
    carrier = models.CharField(max_length=120, blank=True, verbose_name="Transportadora")
    tracking_url = models.URLField(max_length=500, blank=True, verbose_name="Seguimiento")

    shipping_guide = models.CharField(
        max_length=100, blank=True, verbose_name="Número de guía"
    )
    dropi_status = models.CharField(
        max_length=100, blank=True, verbose_name="Estado en Dropi"
    )
    last_dropi_sync = models.DateTimeField(
        null=True, blank=True, verbose_name="Última sync Dropi"
    )

    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Cancelado el")
    cancel_reason = models.CharField(max_length=255, blank=True, verbose_name="Motivo cancelación")
    cancel_pending_dropi = models.BooleanField(
        default=False,
        verbose_name="Pendiente cancelar en Dropi",
    )
    needs_manual_supplier = models.BooleanField(
        default=False,
        verbose_name="Requiere proveedor manual",
        help_text="El proveedor asignado no tenía stock al momento del pedido. "
        "El pedido se creó igual (sin enviarse a Dropi) para reasignarlo a mano "
        "a otro proveedor y confirmarlo desde aquí.",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "Orden"
        verbose_name_plural = "Órdenes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Orden #{self.pk} — {self.name} {self.surname}"

    @property
    def cancel_deadline(self):
        return self.created_at + timedelta(minutes=self.CANCEL_WINDOW_MINUTES)

    def can_cancel(self) -> bool:
        return (
            self.status == self.STATUS_PENDING
            and timezone.now() < self.cancel_deadline
        )

    def get_status_display(self):
        labels = {
            self.STATUS_PENDING: "Pendiente de confirmación",
            self.STATUS_CONFIRMED: "Confirmado",
            self.STATUS_SENT: "Enviado",
            self.STATUS_DELIVERED: "Entregado",
            self.STATUS_CANCELLED: "Cancelado",
        }
        return labels.get(self.status, self.status)

    @property
    def subtotal(self):
        return self.total - self.shipping_cost

    def status_timeline(self) -> list[dict]:
        """Ordered steps for buyer-facing order tracking."""
        steps = [
            (self.STATUS_PENDING, "Pedido recibido"),
            (self.STATUS_CONFIRMED, "Confirmado por logística"),
            (self.STATUS_SENT, "En camino"),
            (self.STATUS_DELIVERED, "Entregado"),
        ]
        status_order = [s[0] for s in steps]
        if self.status == self.STATUS_CANCELLED:
            return [
                {"label": "Pedido recibido", "done": True, "current": False},
                {"label": "Cancelado", "done": True, "current": True},
            ]
        try:
            current_idx = status_order.index(self.status)
        except ValueError:
            current_idx = 0
        timeline = []
        for idx, (_, label) in enumerate(steps):
            timeline.append({
                "label": label,
                "done": idx <= current_idx,
                "current": idx == current_idx,
            })
        return timeline


class CheckoutAttempt(models.Model):
    """Un envío del formulario de compra que NO terminó en pedido.

    Antes estos intentos no quedaban en ningún lado: el cliente veía un error,
    se iba, y el equipo solo se enteraba si escribía por WhatsApp (así se
    perdieron dos ventas en Bogotá en octubre de 2026). Aquí queda qué falló,
    con los datos que el cliente alcanzó a escribir para poder contactarlo.
    """

    STAGE_VALIDATION = "validacion"
    STAGE_UNAVAILABLE = "producto"
    STAGE_ERROR = "error"
    STAGE_CHOICES = [
        (STAGE_VALIDATION, "Datos del formulario"),
        (STAGE_UNAVAILABLE, "Producto no disponible"),
        (STAGE_ERROR, "Error del sistema"),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha")
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, verbose_name="Dónde falló")
    errors = models.JSONField(default=dict, blank=True, verbose_name="Errores",
                              help_text="{campo: [mensajes que vio el cliente]}")
    data = models.JSONField(default=dict, blank=True, verbose_name="Lo que escribió")
    cart = models.JSONField(default=list, blank=True, verbose_name="Carrito")
    detail = models.TextField(blank=True, verbose_name="Detalle técnico")
    order = models.ForeignKey(
        Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="failed_attempts",
        verbose_name="Pedido logrado después",
        help_text="Si el mismo visitante terminó comprando después del error.",
    )

    class Meta:
        verbose_name = "Intento de compra fallido"
        verbose_name_plural = "Intentos de compra fallidos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Intento {self.created_at:%d/%m %H:%M} — {self.get_stage_display()}"
