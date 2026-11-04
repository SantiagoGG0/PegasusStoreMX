# Analisis de Seguridad App y JWT

Fecha: 2026-05-25

Alcance: revision documental y estatica de Pegasus Store / PoC Dropi. No se implemento codigo.

## Diagnostico

La app usa autenticacion tradicional de Django con sesiones, `LoginView`, CSRF y validadores de password. No hay JWT propio para login de usuarios. El unico JWT detectado es el token de integracion Dropi en `dropi_client/client.py`, decodificado para leer `integration_url`; no funciona como autenticacion interna de clientes.

Para esta app Django renderizada con templates, login con sesiones sigue siendo la opcion correcta. Implementar JWT para el login principal no mejora seguridad por si solo y puede empeorarla si se guarda en `localStorage`, se expone a XSS o se omite CSRF. JWT solo conviene si aparece una API separada para SPA/mobile/terceros.

El riesgo mas alto no esta en hashing de passwords, sino en secretos, enlaces publicos de pedidos, ausencia de rate limiting, webhook Dropi, XSS por HTML importado y validaciones server-side incompletas.

## Documento Actual: Password Salting

El documento `Docs/SoftwareEngineerSkills/Seguridad/Seguridad y Criptografia (Password Salting).md` explica bien salt, rainbow tables y algoritmos lentos, pero faltan puntos clave para Django:

- Django ya gestiona salt y formato de hash con sus `PASSWORD_HASHERS`; no se debe implementar salting manual.
- Falta recomendar Argon2 como hasher preferido si se instala dependencia, dejando PBKDF2 como fallback.
- Falta hablar de migracion/upgrade automatico de hashes antiguos al iniciar sesion.
- Falta distinguir salt de `SECRET_KEY`: salt no es secreto; `SECRET_KEY` si lo es y firma sesiones/tokens.
- Falta rate limiting de login/reset como proteccion complementaria contra fuerza bruta.
- Falta politica de contrasenas filtradas: bloquear passwords comunes o comprometidos.
- Falta MFA para admin y cuentas sensibles.
- Falta rotacion de credenciales y secret scanning en repo.
- Falta advertir que pepper complica rotacion y debe vivir fuera de BD, idealmente en secret manager.

## JWT Para Login

Recomendacion: no migrar login web actual a JWT. Mantener sesiones Django endurecidas.

Si se necesita JWT para API/mobile, diseno minimo:

- Usar `djangorestframework-simplejwt`, no JWT manual.
- Access token corto: 5 a 15 minutos.
- Refresh token con rotacion y blacklist.
- Guardar tokens en cookies `HttpOnly`, `Secure`, `SameSite=Lax/Strict`; evitar `localStorage`.
- Proteger refresh/logout con CSRF si usa cookies.
- Validar `iss`, `aud`, expiracion, algoritmo permitido y clave de firma.
- Separar clave JWT de `SECRET_KEY` si el riesgo/escala lo justifica.
- Revocar refresh tokens en cambio de password, logout global o sospecha de compromiso.
- Registrar eventos de login fallido, refresh anomalo y revocacion.

Para Pegasus Store actual, JWT no resuelve los riesgos principales: tokens publicos de pedidos, rate limiting, webhook y XSS.

## Puntos Criticos Detectados

### P0 - Secretos En Repositorio

`comandos.txt` contiene credenciales de correo/panel. Aunque sea PoC, debe tratarse como filtracion.

Riesgo: toma de cuenta, acceso admin, reutilizacion de credenciales.

Accion recomendada:

- Rotar credenciales afectadas.
- Sacar archivo del repo y del historial si ya fue commiteado.
- Agregar `.gitignore`/secret scanning (`gitleaks` o similar).
- Usar `.env` local no versionado y variables de entorno en despliegue.

### P0 - Pedidos Accesibles Por UUID Permanente

`orders.models.Order.access_token` es UUID unico y persistente. `orders.views.order_detail`, `order_confirmation`, `order_cancel` y `order_status_api` aceptan solo posesion del token.

`templates/orders/detail.html` muestra nombre, email, telefono, direccion, guia, transportadora y permite llegar a cancelacion.

Riesgo: si enlace se filtra por email, WhatsApp, historial, logs o `Referer`, tercero ve PII y puede cancelar dentro de ventana.

Accion recomendada:

- Separar token de lectura y token de accion.
- Expirar o rotar tokens sensibles.
- Exigir sesion o magic link verificado para datos completos.
- Requerir confirmacion adicional para cancelar.
- Definir `SECURE_REFERRER_POLICY = "same-origin"` o mas restrictiva.

### P0 - Registro Post-Compra Sin Verificar Email

`accounts.views.signup_after_order` crea cuenta y hace login automatico solo con posesion de `access_token`.

Riesgo: si enlace de pedido se filtra antes de crear cuenta, atacante puede registrar el correo del comprador y vincular pedidos.

Accion recomendada:

- Enviar magic link al email del pedido antes de crear/loguear cuenta.
- No confiar en campo email readonly del formulario como prueba de identidad.
- Vincular pedidos solo tras verificar control del email.

### P1 - Sin Rate Limiting

No hay `django-ratelimit`, `django-axes` ni throttling propio en `requirements.txt`.

Superficies afectadas:

- Login.
- Signup.
- Password reset.
- Magic link de pedidos.
- Checkout.
- Carrito AJAX.
- Webhook.
- `order_status_api` polling.

Riesgo: fuerza bruta, email bombing, enumeracion, abuso de recursos y consumo de API Dropi.

Accion recomendada:

- Rate limit por IP, email, usuario y sesion segun endpoint.
- Lockout progresivo para login/admin.
- Respuestas indistinguibles en recovery/magic link.
- Alertas por volumen anomalo.

### P1 - Webhook Dropi

`orders.views.dropi_webhook` usa `@csrf_exempt`. Valida HMAC solo si `DROPI_WEBHOOK_SECRET` existe; en produccion se exige, pero staging/dev expuestos quedan fragiles.

Riesgo: mutacion de estados por request externo si hay mala config; replay de eventos si no hay timestamp/nonce/event id.

Accion recomendada:

- Exigir firma fuera de localhost.
- Incluir timestamp y ventana anti-replay.
- Guardar event id/idempotency key.
- Validar `shop_order_id` contra `dropi_order_id` esperado.
- Registrar auditoria de eventos rechazados.

### P1 - XSS Por HTML Importado

`catalog.services.dropi_import.upsert_product` guarda descripcion de Dropi. `templates/catalog/detail.html` renderiza `{{ product.description|safe }}`.

`catalog.admin` usa varios `mark_safe` con datos de productos/URLs.

Riesgo: proveedor o dato externo malicioso puede inyectar HTML/JS en tienda o admin.

Accion recomendada:

- Sanitizar HTML permitido con allowlist antes de guardar o renderizar.
- Evitar `|safe` para contenido externo no sanitizado.
- Reemplazar `mark_safe` por `format_html`/`format_html_join`.
- Validar URLs externas de imagen/tracking.

### P1 - Carrito Acepta Cantidades Invalidas

`cart.views.cart_add` y `cart_add_quick` convierten `quantity = int(...)` sin capturar `ValueError`. `Cart.add()` no rechaza cantidad `<= 0`.

Riesgo: POST manual puede causar 500 o guardar cantidades negativas, afectando totales y checkout.

Accion recomendada:

- Validar cantidad con form/servicio server-side.
- Rango permitido: `1..stock`.
- Rechazar no numericos y negativos sin excepcion 500.

### P1 - Checkout No Tiene Idempotencia Persistente

`orders.views.checkout` usa bandera de sesion `checkout_submitting`, crea `Order` y luego llama Dropi, sin `transaction.atomic()` ni clave idempotente persistida.

Riesgo: doble POST/race puede duplicar ordenes o dejar estados locales inconsistentes si falla Dropi/email.

Accion recomendada:

- Mover caso de uso a `CheckoutService`.
- Usar idempotency key persistida.
- Usar transaccion acotada para orden local.
- Dejar llamadas Dropi/email fuera de transaccion, con outbox/reintento si escala.

### P2 - Cookies, Headers y Sesion Incompletos

`config.settings` activa HSTS, SSL redirect y cookies secure cuando `DEBUG=False`, pero faltan declaraciones explicitas:

- `SESSION_COOKIE_HTTPONLY`.
- `SESSION_COOKIE_SAMESITE`.
- `CSRF_COOKIE_SAMESITE`.
- `SESSION_COOKIE_AGE`.
- `SECURE_REFERRER_POLICY`.
- `SECURE_CROSS_ORIGIN_OPENER_POLICY` si aplica.

Accion recomendada: declarar defaults seguros aunque Django tenga valores por defecto, para que la politica quede auditable.

### P2 - Archivos Subidos

`accounts.models.CustomerProfile.avatar` permite imagen de perfil. `AvatarUploadForm` usa `ImageField`, buen inicio, pero falta politica explicita de tamano, dimensiones, formato real y limpieza.

Riesgo: consumo de almacenamiento, archivos malformados, DoS por imagen grande.

Accion recomendada:

- Limitar peso maximo.
- Validar dimensiones.
- Normalizar/reprocesar imagen.
- Servir media desde storage/CDN con headers correctos.

### P2 - Datos Personales y Logs

Pedidos guardan email, telefono, direccion y notas. Logs actuales registran IDs y errores; cuidado con excepciones de proveedores que puedan traer payloads.

Accion recomendada:

- No loguear PII ni tokens.
- Enmascarar email/telefono en logs.
- Definir retencion de pedidos y datos personales.
- Revisar politica de privacidad contra datos realmente almacenados.

## Capas / SOLID

La app ya tiene servicios (`orders.services`, `cart.Cart`, `catalog.services`) pero aun hay vistas pesadas.

Mejor direccion:

- Views: HTTP, auth, mensajes, render/redirect.
- Forms: validacion de borde.
- Services: checkout, cancelacion, magic links, webhook.
- Selectors: lecturas de pedidos/dashboard.
- Models: persistencia e invariantes simples.

Prioridad arquitectonica:

- `CheckoutService.create_order(...)`.
- `OrderAccessService` para magic links/tokens.
- `WebhookService.process_dropi_event(...)`.
- `CartLineForm` o servicio de validacion de cantidad.

## UX / Seguridad

Mantener identidad Pegasus y patrones UI actuales. Seguridad debe sentirse como confianza, no friccion innecesaria.

- Para pedidos invitados: magic link por email antes de mostrar PII completa.
- Para cancelacion: pedir confirmacion clara y, si no hay sesion, validar token de accion corto.
- Para errores auth/reset: mensajes neutros, sin enumerar cuentas.
- Para rate limit: mostrar mensaje humano y contacto WhatsApp si aplica.

## Roadmap Recomendado

### Ahora

- Rotar secretos de `comandos.txt` y eliminar archivo sensible.
- No implementar JWT para login web.
- Definir politica de sesiones/cookies/headers en `settings`.
- Bloquear `|safe` sobre descripcion Dropi hasta tener sanitizacion.
- Validar cantidad del carrito server-side.

### Siguiente

- Endurecer acceso a pedidos: magic link verificado, tokens por accion, expiracion.
- Rate limit en login/reset/magic link/checkout/status API.
- Webhook con firma obligatoria, timestamp, idempotencia y auditoria.
- Extraer checkout a service transaccional con idempotency key.

### Luego

- MFA para admin.
- Secret scanning en CI.
- Dependency scanning.
- Politica de retencion de PII.
- Sanitizacion centralizada de contenido externo.
- Observabilidad de seguridad: login fallido, rate limit, webhook rechazado, token invalido.

## Veredicto

No falta salting manual: Django ya cubre hashing seguro si se usan password hashers correctos. Tampoco conviene JWT para login web actual.

Faltan controles alrededor del flujo real de negocio: secretos, PII en pedidos por token, verificacion de email, rate limiting, webhook robusto, XSS por contenido externo, validacion de carrito e idempotencia de checkout. Esos puntos dan mayor reduccion de riesgo que migrar auth a JWT.
