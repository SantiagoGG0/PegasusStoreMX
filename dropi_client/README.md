# Dropi API client

## Cancelación de pedidos

`DropiClient.cancel_order()` prueba varios endpoints documentados de forma informal en integraciones:

- `PUT orders/myorders/{dropi_order_id}` con `status: CANCELADO`
- `POST orders/cancel`
- `POST orders/myorders/{id}/cancel`

Si ninguno responde con éxito, la tienda marca el pedido como cancelado localmente y deja `cancel_pending_dropi=True` para que un operador cancele manualmente en el panel de Dropi.

Consulta la documentación oficial de Dropi para el endpoint definitivo de tu integración.
