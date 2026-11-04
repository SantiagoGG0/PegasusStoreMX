# SPEC de contexto — PoC_Dropi (para asistentes / Claude)

Documento orientado a modelos: stack, dominio de negocio, flujos y convenciones del repo. Actualizar si cambian dependencias o integración Dropi.

---

## 1. Qué es el proyecto

- **Nombre / tipo:** PoC de **e‑commerce** en Django integrado con **Dropi** (ecosistema de dropshipping / catálogo y logística orientado a Colombia y LATAM).
- **Objetivo funcional:** Catálogo público, carrito en sesión, checkout que **crea pedidos en la API de Dropi** y guarda copia local en BD.
- **No es:** Pasarela de pago propia, panel completo de dropshipper, ni multi‑tenant. Es una **PoC** con foco en catálogo + pedido hacia Dropi.

---

## 2. Dropi (contexto de negocio)

- **Dropi** actúa como proveedor de catálogo, stock y creación de órdenes vía API de integraciones (`https://api.dropi.co/integrations/` por defecto).
- El integrador importa productos a su “tienda” local, define **precio de venta** sobre el **costo** que devuelve Dropi, activa visibilidad y puede registrar productos en la **lista de importación** de Dropi para que los pedidos referencien el producto local (slug / id).
- **Autenticación:** header `dropi-integration-key` con el token de integración (JWT en la práctica).
- **Detalle crítico de implementación:** `DropiClient` decodifica el payload del JWT (sin verificar firma) para leer `integration_url` y arma un `User-Agent` tipo `WordPress/6.5; {integration_url}` porque Dropi valida peticiones contra esa URL (compatibilidad con flujo tipo WordPress/WooCommerce).

---

## 3. Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Lenguaje | Python (proyecto probado con **3.10**; `requirements.txt` fija **Django 5.2.x** porque Django 6 exige Python ≥3.12) |
| Framework web | **Django** `>=5.2,<6` |
| Config / secretos | **python-decouple** (`config/settings.py` lee `.env`) |
| HTTP cliente API | **requests** (sesión con headers Dropi) |
| Imágenes | **Pillow** (dependencia típica Django + imágenes) |
| BD | **SQLite** (`db.sqlite3` en raíz del proyecto) |
| Sesiones | Backend por defecto Django (carrito en sesión) |
| Estáticos | `STATIC_URL`, `STATICFILES_DIRS` → `static/`, `STATIC_ROOT` → `staticfiles/`; `collectstatic` en despliegue |
| Media | `MEDIA_ROOT` / `MEDIA_URL` (URLs servidas en desarrollo vía `config/urls.py`) |
| Plantillas | Django Templates (`templates/`, `templates/admin/`) |
| Admin | Django Admin **muy usado** para sync/import Dropi (ver `catalog/admin.py`) |

**Dependencias declaradas:** ver `requirements.txt` en la raíz del repo.

---

## 4. Estructura de apps Django

| App | Rol |
|-----|-----|
| `config` | `settings`, `urls`, `wsgi`, `asgi` |
| `dropi_client` | Cliente HTTP `DropiClient`: productos, categorías, bodegas, crear orden, `mark_imported`. Excepción `DropiAPIError`. |
| `catalog` | Modelos `Category`, `Product` (campos Dropi + precio tienda, slug, `is_active`, `is_featured`). Vistas tienda: listado, detalle, variantes. **Admin:** sync masiva, explorar catálogo Dropi, import por URL/ID, acciones activar/desactivar, registrar en import list. |
| `cart` | Carrito basado en **sesión** (`Cart` en `cart/cart.py`), clave `CART_SESSION_ID` en settings. Soporta `variation_id`. |
| `orders` | Modelo `Order` (datos cliente, total, JSON `items`, `dropi_order_id`, estados). Vista `checkout` arma payload Dropi y llama `create_order`. |

---

## 5. Rutas URL (usuario final)

- Raíz `""` → `catalog` (tienda).
- `carrito/` → carrito.
- `pedidos/` → checkout y confirmación.
- `admin/` → Django Admin (operaciones Dropi y catálogo).

Detalle de producto: `producto/<slug>/` (ver `catalog/urls.py`, nombre `catalog:detail`).

---

## 6. Variables de entorno relevantes

Definidas vía `.env` y `python-decouple` en `config/settings.py`:

- `SECRET_KEY` — obligatorio.
- `DEBUG` — bool.
- `ALLOWED_HOSTS` — CSV.
- `DROPI_TOKEN` — token integración Dropi (JWT).
- `DROPI_BASE_URL` — default `https://api.dropi.co/integrations/`.

**No commitear** `.env` con secretos reales.

---

## 7. Flujo principal (datos)

1. **Admin** sincroniza o importa productos desde Dropi → upsert en `Product` (costo, stock, imágenes JSON, variantes JSON, categoría).
2. Admin ajusta **precio de venta**, **is_active**, **is_featured**; opcional **Registrar en Dropi (import list)**.
3. **Cliente** navega catálogo, añade al carrito (sesión), checkout con formulario.
4. **Backend** construye payload para `POST orders/myorders`, envía con `DropiClient`, lee `dropi_order_id` de la respuesta, persiste `Order`, vacía carrito.

Métodos de pago en modelo local alineados a terminología Dropi: `CON RECAUDO` / `SIN RECAUDO` (contra entrega / anticipado en UI).

---

## 8. Internacionalización y zona

- `LANGUAGE_CODE = 'es-co'`
- `TIME_ZONE = 'America/Bogota'`

Mensajes de usuario y admin en español en gran parte del código.

---

## 9. Testing / calidad

- Apps tienen `tests.py` (cobertura variable); al cambiar checkout o cliente Dropi, conviene tests o pruebas manuales contra sandbox/token válido.

---

## 10. Documentación de diseño en repo

- `Docs/Specs/UIUX-PATTERNS.md` — patrones UI/UX del proyecto (muy extenso). Para cambios de front/plantillas, consultar coherencia con ese doc.

---

## 11. Limitaciones conscientes (PoC)

- SQLite no ideal para producción concurrente.
- `runserver` solo desarrollo; producción requiere WSGI (p. ej. Gunicorn) + proxy y variables seguras.
- Carrito en sesión (tamaño, no compartido entre dispositivos).
- Checkout incluye logs de depuración (`logger.warning` con carrito); revisar antes de producción.

---

## 12. Cómo usar esta SPEC en un prompt

Copiar secciones 1–7 como contexto fijo al pedir cambios en integración Dropi, admin de catálogo, checkout o despliegue. Para UI, añadir referencia a `UIUX-PATTERNS.md`.
