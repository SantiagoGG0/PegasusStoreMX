# Pegasus Store México: pendientes antes de lanzar

Proyecto separado de Pegasus Store Colombia: misma lógica de negocio, cuenta
de Dropi México propia (otro token, catálogo y proveedores).

## Ya adaptado
- API de Dropi México (`api.dropi.mx`), sin el filtro `userVerified` (en
  México dejaba ~34 productos; sin él hay entre 5.000 y 10.000 con stock).
- Moneda MXN, `es-mx`, hora de Ciudad de México, precios con coma ($1,299).
- Redondeo de precios terminado en 9 (129, 1,299). El de Colombia (…900)
  subía un producto de $127 a $900.
- Checkout: código postal obligatorio que llena estado y municipio, 32
  estados con códigos ISO, municipios con contra entrega de Dropi México
  (`cart/data/mexico_geo.json`), celular de 10 dígitos con +52 / 044 / 045.
- El pedido a Dropi lleva `country: MX` y los nombres de estado y ciudad de
  Dropi (`cart/mexico_geo.dropi_names`).
- WhatsApp y Twilio con +52. Google Ads y Clarity configurables (antes estaban
  fijos los IDs de Colombia).
- Textos: todo México, repartidor, efectivo, RFC, Profeco, leyes mexicanas.
- Páginas legales escritas para México (términos, aviso de privacidad,
  devoluciones y garantía, propiedad intelectual): LFPC art. 56 (5 días
  hábiles para revocar, flete de devolución a cargo del cliente), art. 77
  (garantía mínima de 90 días) y LFPDPPP de 2025 (ARCO, Secretaría
  Anticorrupción y Buen Gobierno). Los datos vacíos de la tienda no se muestran.
- Guía real de Dropi México (2026-11-04): misma tarifa en Mexicali y CDMX
  (Quality-post 149, Veloces 162, Tiui 170, Coordi 188). Se usa 188 en las
  zonas A y B.

## Provisional: recalibrar con datos reales
- **Costo de guía** (`SHIPPING_ZONE_A/B_COST` = 188): la más cara de las
  cotizadas. Si en Dropi se fija una paquetería predeterminada, bajar a su
  tarifa. Confirmar si Dropi cobra además una comisión por recaudo.
- **Escalera de ganancia mínima** (`PRICING_MIN_GAIN_LADDER`): conversión de
  la de Colombia (~215 COP por MXN).
- **Tasa de rechazo contra entrega** (`COD_REJECTION_RATE` = 20%): recalcular
  con los primeros pedidos cerrados.
- **Zonas** (`cart/shipping.py`, `MEXICO_CITIES`): zona A por tamaño de
  ciudad; zona C vacía. Ajustar con las guías reales.
- **Transportadoras de respaldo** (`orders/services.CARRIER_FALLBACKS`):
  vacía. Llenar con las de la cuenta de Dropi México y sus IDs.

## Falta hacer
- Dominio `pegasusstoremx.com` (se compra al final; pasos en `Docs/DOMINIO-PASOS.md`). Mientras tanto la dirección temporal está cerrada a Google. Dominio de México (vacío por ahora) y token de Dropi México registrado con
  ese dominio (hoy el token dice `www.pegasusstoreco.com`).
- Datos de la tienda (vacíos por ahora): razón social, RFC, dirección,
  WhatsApp +52 y correo (admin → Configuración de la tienda, o `STORE_*`).
  El aviso de privacidad pide identidad y domicilio del responsable: llenarlos
  antes de lanzar y hacer revisar los textos legales por un abogado.
- Colonia: ya es un campo aparte en el checkout (`Order.colonia`) y se manda a
  Dropi dentro de `dir` ("Calle 1, Col. Centro"). En el primer pedido real,
  ver en Dropi si aparece en su campo Colonia; si la API tiene un campo
  propio, agregarlo al payload en orders/views.py.
- Infraestructura: base Neon nueva, app nueva en DigitalOcean (`.do/app.yaml`),
  secrets de GitHub Actions. Los workflows programados están pausados.
- GA4, Google Ads, Merchant Center, Meta y Search Console propios de México.
- Primera importación del catálogo y colecciones (`collections_seed.py` tiene
  palabras clave pensadas para el catálogo colombiano: revisar con el de
  México). Exclusiones SEO: regenerar con `catalog/data/build_seo_exclusions.py`.
- Un pedido de prueba real a 3-4 estados antes de pautar (la creación de
  pedidos en Dropi México todavía no se probó con un pedido real).
