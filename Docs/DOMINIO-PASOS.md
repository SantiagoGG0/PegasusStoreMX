# Conectar el dominio pegasusstoremx.com

Hasta entonces la tienda vive en `monkfish-app-6bpr3.ondigitalocean.app`,
cerrada a Google (robots.txt `Disallow: /` y `X-Robots-Tag: noindex` en todo
host `*.ondigitalocean.app`). Con el dominio propio queda abierta sola.

## 1. Comprar
`pegasusstoremx.com` (libre al 2026-11-04). Opcional y barato si se puede:
`pegasusstore.mx` para redirigirlo al principal. `pegasusstore.com.mx` ya
tiene dueño.

## 2. DigitalOcean: agregar el dominio
monkfish-app → Settings → Domains → Add domain → `www.pegasusstoremx.com`
(y también `pegasusstoremx.com`). DigitalOcean muestra los registros DNS:
- Si dejas que DigitalOcean maneje el DNS: cambia los nameservers en el
  registrador por los de DigitalOcean.
- Si no: crea en el registrador el CNAME `www` → `monkfish-app-6bpr3.ondigitalocean.app`
  y, para el dominio sin www, lo que DigitalOcean indique (ALIAS/ANAME o A).
El certificado HTTPS lo emite DigitalOcean solo (minutos a un par de horas).

## 3. DigitalOcean: variables (Settings → App-Level Environment Variables)
```
ALLOWED_HOSTS=www.pegasusstoremx.com,pegasusstoremx.com,monkfish-app-6bpr3.ondigitalocean.app
CSRF_TRUSTED_ORIGINS=https://www.pegasusstoremx.com,https://pegasusstoremx.com
STORE_SITE_URL=https://www.pegasusstoremx.com
LEGACY_HOSTS=pegasusstoremx.com,monkfish-app-6bpr3.ondigitalocean.app
```
`LEGACY_HOSTS` hace que el dominio sin www y la dirección temporal redirijan
(301) a `https://www.pegasusstoremx.com`. El webhook de Dropi no se redirige.

## 4. Dropi México
- Integración → cambiar la URL de la tienda a `https://www.pegasusstoremx.com`
  y generar un token nuevo (el actual dice `www.pegasusstoreco.com`).
- Reemplazar `DROPI_TOKEN` en DigitalOcean, en los secrets de GitHub Actions
  y en el `.env` local.
- Webhook: `https://www.pegasusstoremx.com/pedidos/webhook/` con el valor de
  `DROPI_WEBHOOK_SECRET`.

## 5. Google
- Search Console: propiedad de dominio `pegasusstoremx.com`, enviar
  `https://www.pegasusstoremx.com/sitemap.xml`.
- Merchant Center (México, MXN): feed `https://www.pegasusstoremx.com/feeds/google-merchant.xml`.
- GA4, Google Ads, Meta: cuentas de México y sus IDs en las variables
  `GA4_MEASUREMENT_ID`, `GOOGLE_ADS_ID`, `GOOGLE_ADS_PURCHASE_SEND_TO`,
  `META_PIXEL_ID`.

## 6. Comprobar
- `https://www.pegasusstoremx.com/robots.txt` debe decir `Allow: /` y traer el sitemap.
- `https://monkfish-app-6bpr3.ondigitalocean.app/` debe redirigir al dominio.
- Un pedido de prueba real (ver MEXICO-PENDIENTES.md).
