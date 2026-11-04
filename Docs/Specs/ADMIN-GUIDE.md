# Guía de administración — Pegasus Store

## Primer acceso

```bash
python manage.py createsuperuser
```

Abre `http://127.0.0.1:8765/admin/` (o el puerto configurado) e inicia sesión con el superusuario.

**No enlaces `/admin/` en el sitio público** (seguridad).

## Qué gestionar

### Catálogo (`catalog`)

- **Productos:** precios, stock, imágenes, activar/desactivar.
- **Categorías:** organización del catálogo.
- **Sync Dropi:** importar y actualizar productos desde Dropi.

### Pedidos (`orders`)

- Estados: pendiente, confirmado, enviado, entregado, cancelado.
- `dropi_order_id`: referencia en Dropi.
- `cancel_pending_dropi`: requiere cancelación manual en panel Dropi.
- Enlace **Ver página** → confirmación del cliente (token seguro).

**Cancelaciones automáticas:** el cliente tiene 15 minutos tras la compra si el pedido sigue en «Pendiente de confirmación». Fuera de ese plazo, usa la acción «Marcar como cancelado» y cancela en Dropi si aplica.

### Usuarios (`auth` / `accounts`)

- Clientes con cuenta: `User` con email como username.
- `CustomerProfile`: datos opcionales del cliente.
- Staff: marca `is_staff` para acceso al admin (no mezclar con clientes).

## Variables `.env`

| Variable | Uso |
|----------|-----|
| `DROPI_TOKEN` | API Dropi |
| `DROPI_WEBHOOK_SECRET` | Firma webhook (opcional) |
| `DEFAULT_FROM_EMAIL` | Correos de pedidos |
| `EMAIL_*` | SMTP |

## Grupo operador (opcional)

Crea un grupo «Operador tienda» con permisos:

- `catalog` — ver y cambiar productos/categorías
- `orders` — ver y cambiar órdenes

Sin permisos de `auth` salvo lectura de usuarios si lo necesitas.

## URLs útiles (desarrollo)

| Ruta | Descripción |
|------|-------------|
| `/admin/` | Panel Django |
| `/pedidos/mis-pedidos/` | Vista cliente |
| `/cuenta/entrar/` | Login cliente |
| `/ayuda/` | Centro de ayuda |
