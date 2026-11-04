from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def _video_storage():
    """Return RawMediaCloudinaryStorage when Cloudinary is active (accepts mp4/webm),
    otherwise fall back to default file system storage."""
    if getattr(settings, 'USE_CLOUDINARY', False):
        try:
            from cloudinary_storage.storage import RawMediaCloudinaryStorage
            return RawMediaCloudinaryStorage()
        except ImportError:
            pass
    from django.core.files.storage import FileSystemStorage
    return FileSystemStorage()


class Category(models.Model):
    dropi_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        verbose_name='Categoría padre',
        help_text='Deja vacío para categorías principales. Selecciona una categoría padre para crear una subcategoría.',
    )
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        verbose_name='Imagen',
        help_text='Imagen circular representativa (recomendado: 300×300 px, formato cuadrado).',
    )

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} › {self.name}"
        return self.name

    @property
    def is_root(self):
        return self.parent_id is None


# ── Exclusión SEO / campañas (lote C2) ─────────────────────────────────────────
# Criterios asignados por slug con `manage.py load_seo_exclusions`.
SEO_EXCLUSION_CHOICES = [
    ("b", "Basura o servicio (envío, garantía, placeholder)"),
    ("c1", "Claim de salud o adelgazamiento en el nombre"),
    ("c2", "Suplemento ingerible"),
    ("c3", "Claim de salud en la descripción"),
    ("a1", "Marca registrada o réplica"),
    ("e", "Armas o producto para adultos"),
]
# Fuera del sitemap y con noindex,follow en la ficha.
SEO_NOINDEX_EXCLUSIONS = frozenset({"b", "c1", "c2", "c3", "a1", "e"})
# Fuera de las listas del home, categorías y búsqueda (y de campañas). Hoy
# coincide con SEO_NOINDEX_EXCLUSIONS; se mantienen separados por si un
# criterio futuro solo debe salir de listas.
LISTING_EXCLUSIONS = SEO_NOINDEX_EXCLUSIONS


PRICING_STATUS_CHOICES = [
    ("envio_gratis", "Envío gratis (el margen cubre la guía)"),
    ("envio_pagado", "El cliente paga parte o toda la guía"),
    ("bajo_margen", "Margen menor al mínimo por pedido"), ("sin_costo", "Sin costo en Dropi"),
]

INACTIVE_REASON_CHOICES = [
    ("sin_stock", "Sin stock en Dropi"),
    ("no_existe", "Ya no está en el catálogo de Dropi"),
    ("sin_imagenes", "Sin imágenes válidas"),
    ("precio_bajo", "Precio por debajo del mínimo para venderse solo"),
]


class ProductQuerySet(models.QuerySet):
    def listable(self):
        """Productos que pueden aparecer en listas (home, categorías, búsqueda)."""
        return self.exclude(seo_exclusion__in=LISTING_EXCLUSIONS)

    def indexable(self):
        """Productos que van al sitemap: sin noindex y que no son un duplicado
        con rel=canonical a otra ficha."""
        return self.exclude(seo_exclusion__in=SEO_NOINDEX_EXCLUSIONS).filter(canonical_product__isnull=True)


class Product(models.Model):
    # ── Dropi data ───────────────────────────────────────────────────────────
    dropi_id = models.PositiveIntegerField(unique=True, verbose_name="ID en Dropi")
    supplier_id = models.PositiveIntegerField(default=0, verbose_name="ID proveedor")
    name = models.CharField(max_length=500, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
        verbose_name="Categoría Pegasus",
        help_text="Categoría curada visible en tienda. No depende directamente de Dropi.",
    )
    dropi_category_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID categoría Dropi",
    )
    dropi_category_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Categoría Dropi original",
    )
    category_confidence = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
        verbose_name="Confianza categoría",
    )
    category_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Razón de categorización",
    )
    category_locked = models.BooleanField(
        default=False,
        verbose_name="Bloquear categoría",
        help_text="Si está activo, la sincronización de Dropi no cambia la categoría Pegasus.",
    )
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Costo Dropi",
    )
    stock = models.IntegerField(default=0, verbose_name="Stock")
    images = models.JSONField(default=list, verbose_name="Imágenes")
    variants = models.JSONField(default=list, verbose_name="Variantes")

    # ── Store data (defined by admin) ────────────────────────────────────────
    slug = models.SlugField(max_length=600, unique=True, blank=True)
    video_url = models.URLField(
        blank=True,
        verbose_name="Video URL",
        help_text="URL de YouTube, Vimeo o video directo (.mp4). Se muestra en la galería del producto.",
    )
    video_file = models.FileField(
        upload_to="products/videos/",
        blank=True,
        null=True,
        storage=_video_storage,
        verbose_name="Video (archivo)",
        help_text="Sube un archivo de video (.mp4, .webm). Tiene prioridad sobre el Video URL.",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Precio de venta",
        help_text="Define tu precio de venta. Tu ganancia = precio - costo Dropi.",
    )
    display_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Nombre visible",
        help_text=(
            "Nombre que ve el cliente (tarjetas, ficha, Google). Lo llena "
            "`manage.py clean_product_names` sin cortes de Dropi ni etiquetas "
            "internas; puedes editarlo a mano y la sincronización no lo toca. "
            "Vacío = se limpia el nombre de Dropi al vuelo."
        ),
    )
    meta_title = models.CharField(
        max_length=70,
        blank=True,
        verbose_name="Meta title (SEO)",
        help_text="Título para motores de búsqueda. Máx. 70 caracteres. Si está vacío se usa el nombre del producto.",
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Meta description (SEO)",
        help_text="Descripción para motores de búsqueda. Máx. 160 caracteres.",
    )
    description_unique = models.TextField(
        blank=True,
        verbose_name="Descripción extendida (única)",
        help_text=(
            "Texto propio generado por plantillas (ver "
            "catalog/services/content_generation.py), distinto al crudo del "
            "proveedor. Cuando está poblado, reemplaza la descripción cruda "
            "de Dropi en el detalle de producto. Vacío = se sigue mostrando "
            "la descripción cruda tal como hoy."
        ),
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name="Visible en tienda",
        help_text="Solo los productos activos aparecen en la tienda.",
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name="Destacado",
        help_text="Aparece en 'Los favoritos de la tienda' en el home.",
    )
    is_new_arrival = models.BooleanField(
        default=False,
        verbose_name="Recién llegado",
        help_text="Aparece en 'Recién llegados' en el home.",
    )
    image_flagged = models.BooleanField(
        default=False,
        verbose_name="Imagen irrelevante",
        help_text="La imagen no corresponde al producto. Se oculta del catálogo aunque esté activo.",
    )

    seo_exclusion = models.CharField(
        max_length=4,
        blank=True,
        db_index=True,
        choices=SEO_EXCLUSION_CHOICES,
        verbose_name="Exclusión SEO / campañas",
        help_text="Lo asigna `manage.py load_seo_exclusions`. No desactiva el producto ni cambia su URL.",
    )
    canonical_product = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
        verbose_name="Ficha canónica (duplicado de)",
        help_text="Casi duplicado: la ficha declara rel=canonical hacia este producto y sale del sitemap.",
    )

    # ── Reseñas (agregados desnormalizados; ver ProductReview + services) ───
    rating_average = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Valoración media",
        help_text="Recalculado al publicar reseñas. Vacío = sin opiniones reales.",
    )
    rating_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Número de reseñas",
    )

    # ── Precio / ranking (ver catalog/services/pricing.py y ranking.py) ─────
    suggested_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Precio sugerido Dropi",
        help_text="Referencia de mercado que publica el proveedor en Dropi.",
    )
    price_locked = models.BooleanField(
        default=False,
        verbose_name="Precio fijado a mano",
        help_text="El recálculo automático de precios no toca este producto.",
    )
    pricing_status = models.CharField(
        max_length=16,
        blank=True,
        db_index=True,
        choices=PRICING_STATUS_CHOICES,
        verbose_name="Estado de precio",
    )
    rank_score = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        verbose_name="Puntaje de relevancia",
        help_text="0-100. Ordena el catálogo por defecto (rentabilidad × calidad × categoría).",
    )
    inactive_reason = models.CharField(
        max_length=24,
        blank=True,
        choices=INACTIVE_REASON_CHOICES,
        verbose_name="Motivo de despublicación automática",
        help_text="Lo asignan los comandos de sync. Vacío = activo o despublicado a mano.",
    )
    gallery_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Galería sincronizada",
        help_text="Última vez que se trajo la galería completa desde el detalle de Dropi.",
    )

    # ── Metadata ─────────────────────────────────────────────────────────────
    last_synced = models.DateTimeField(auto_now=True, verbose_name="Última sync")

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "-last_synced"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            if not base_slug:
                # Fallback for names that slugify to empty (e.g. punctuation-only).
                base_slug = f"producto-{self.dropi_id}" if self.dropi_id else "producto"
            slug = base_slug
            n = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def shown_name(self) -> str:
        """Nombre para mostrar: el curado (display_name) o el de Dropi limpio."""
        if self.display_name:
            return self.display_name
        from .services.naming import clean_display_name

        return clean_display_name(self.name)

    def get_absolute_url(self):
        return reverse("catalog:detail", kwargs={"slug": self.slug})

    @property
    def display_rating_is_real(self) -> bool:
        return self.rating_count > 0 and self.rating_average is not None

    @property
    def display_rating(self) -> float | None:
        """Real average rating, or None until the product has published reviews.
        No fabricated placeholder — showing stars without real reviews behind
        them is misleading to buyers."""
        if self.display_rating_is_real:
            return float(self.rating_average)
        return None

    @property
    def display_rating_full_stars(self) -> int:
        if self.display_rating is None:
            return 0
        return int(self.display_rating)

    @property
    def display_rating_has_half(self) -> bool:
        if self.display_rating is None:
            return False
        return (self.display_rating - self.display_rating_full_stars) >= 0.3

    @property
    def main_image(self):
        from urllib.parse import urlsplit, urlunsplit, quote
        def _safe_url(raw):
            if not raw:
                return ""
            parts = urlsplit(raw)
            safe_path = quote(parts.path, safe="/:@!$&'()*+,;=")
            return urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))
        if self.images:
            first = self.images[0]
            if isinstance(first, dict):
                raw = first.get("url") or first.get("image") or first.get("src") or ""
            else:
                raw = str(first)
            return _safe_url(raw)
        return ""

    @property
    def display_main_image(self) -> str:
        """Best single thumbnail: an admin-uploaded custom image takes priority
        over the raw Dropi feed image (main_image), so staff-curated photos show
        up everywhere a single thumbnail is needed (cart drawer, hero, buy bar)."""
        custom = self.custom_images.first()
        if custom and custom.image:
            return custom.image.url
        return self.main_image

    @property
    def card_variants_json(self):
        """Minimal [{id, label}] JSON for in-card variant picker."""
        import json
        result = []
        for v in (self.variants or []):
            if not isinstance(v, dict):
                continue
            # Individual SKU structure
            if "attribute_values" in v or "warehouse_product_variation" in v:
                vid = v.get("id")
                if not vid:
                    continue
                attrs = v.get("attribute_values") or []
                label_parts = [a.get("value", "") for a in attrs if isinstance(a, dict)]
                label = " / ".join(label_parts) or f"Variante {vid}"
                stock = sum(
                    w.get("stock", 0)
                    for w in (v.get("warehouse_product_variation") or [])
                    if isinstance(w, dict)
                )
                if stock > 0:
                    result.append({"id": vid, "label": label})
            # Attribute group structure
            elif "values" in v:
                attr_name = v.get("description", "")
                for val in (v.get("values") or []):
                    if not isinstance(val, dict):
                        continue
                    val_id = val.get("id")
                    val_name = val.get("value", "")
                    if not val_id:
                        continue
                    label = f"{attr_name}: {val_name}" if attr_name else val_name
                    result.append({"id": val_id, "label": label})
        return json.dumps(result, ensure_ascii=False)

    @property
    def profit(self):
        return self.price - self.cost

    @property
    def seo_noindex(self):
        return self.seo_exclusion in SEO_NOINDEX_EXCLUSIONS

    @property
    def hidden_from_listings(self):
        return self.seo_exclusion in LISTING_EXCLUSIONS

    @property
    def excluded_from_ads(self):
        """No usar en campañas (Google Ads, Merchant Center, Meta, TikTok)."""
        return self.seo_exclusion in LISTING_EXCLUSIONS

    @property
    def likely_free_shipping(self):
        """Badge 'Envío gratis' en catálogo (antes de conocer la ciudad del
        comprador): solo cuando el margen cubre la guía más cara en uso
        (cart.shipping.max_guide_cost) más la ganancia mínima del producto
        (pricing.min_gain), así el envío es gratis en cualquier municipio.
        Ver cart/shipping.py para el cálculo real por ciudad."""
        from cart.shipping import max_guide_cost

        from .services.pricing import min_gain

        return self.profit >= max_guide_cost() + min_gain(self.cost)

    @property
    def expected_net_profit(self):
        """Ganancia neta esperada por unidad vendida, en MXN.

        Modelo híbrido (ver catalog/services/pricing.py): en un pedido
        ENTREGADO la tienda gana margen − guía si el envío es gratis, o la
        ganancia mínima del producto (o todo el margen, si es menor) cuando
        el comprador paga parte o toda la guía. En un pedido COD RECHAZADO no
        hay ingreso y se pierde settings.COD_REJECTION_LOSS.

        Usa el costo de guía de Zona A (el más bajo) como escenario base —
        es una aproximación a nivel catálogo; el cálculo exacto por ciudad
        vive en cart/shipping.py, que se aplica en el carrito real.
        """
        from .services.pricing import expected_net_profit, min_gain

        return expected_net_profit(self.price - self.cost, min_gain(self.cost))

    @property
    def shipping_gap(self):
        """Pesos que vería el comprador como cargo de envío en checkout, en
        el escenario más barato (Zona A), comprando solo este producto (ver
        cart/shipping.py). No es un %, es plata real sumada al total del
        pedido — eso es lo que rompe la conversión, no qué tan alto sea el %
        de envío sobre un producto barato."""
        from django.conf import settings

        from .services.pricing import min_gain, shipping_charged

        return shipping_charged(self.price - self.cost, settings.SHIPPING_ZONE_A_COST, min_gain(self.cost))

    @property
    def needs_combo(self):
        """Regla 1 (techo): el cargo de envío que vería el comprador supera
        el techo tolerable (settings.SHIPPING_CEILING). Ningún ajuste de
        precio arregla esto solo — candidato a combo con otro producto del
        catálogo, nunca a despublicación automática."""
        from decimal import Decimal
        from django.conf import settings
        return self.shipping_gap > Decimal(str(settings.SHIPPING_CEILING))

    @property
    def margin_percent(self):
        """Margen como fracción sobre el costo Dropi (0.30 = 30%). None si
        el costo es 0 (indefinido, no se puede calcular %)."""
        if not self.cost:
            return None
        return float((self.price - self.cost) / self.cost)

    @property
    def is_profitable(self):
        """Regla de rentabilidad en 3 pasos (ver settings.py para los
        umbrales configurables):

        1. Por encima del techo de envío (needs_combo=True) → nunca
           'profitable' aquí. No es un fallo de precio, es que el producto
           no se sostiene solo; requiere combo (ver
           catalog/services/combo_suggestions.py), decidido a mano.
        2. Bajo el techo → deben cumplirse DOS pisos a la vez, no uno solo:
           ganancia neta esperada en pesos (expected_net_profit, ya
           descuenta rechazo COD, >= MIN_NET_PROFIT) Y margen % mínimo
           (MIN_MARGIN_PERCENT).
           Un producto con gran % pero poca plata de costo bajo, o mucha
           plata de margen sobre un costo inflado con % ínfimo, no cuentan
           como sanos por sí solos.
        """
        from decimal import Decimal
        from django.conf import settings

        if self.needs_combo:
            return False
        if self.expected_net_profit < Decimal(str(settings.MIN_NET_PROFIT)):
            return False
        mp = self.margin_percent
        if mp is None or mp < settings.MIN_MARGIN_PERCENT:
            return False
        return True

    @property
    def profitability_status(self):
        """Una de 'profitable' / 'needs_combo' / 'unprofitable' — resumen
        de las 3 reglas para reportes y admin."""
        if self.needs_combo:
            return "needs_combo"
        if self.is_profitable:
            return "profitable"
        return "unprofitable"


class ProductImage(models.Model):
    """Custom images uploaded by the store admin, overriding Dropi images in product detail."""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="custom_images",
        verbose_name="Producto",
    )
    image = models.ImageField(
        upload_to="products/",
        verbose_name="Imagen",
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Menor número = aparece primero.",
    )

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "Imagen personalizada"
        verbose_name_plural = "Imágenes personalizadas"

    def __str__(self):
        return f"{self.product.name} – imagen {self.order}"


class ProductVideo(models.Model):
    """Videos uploaded by the store admin, shown in the product detail gallery."""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="custom_videos",
        verbose_name="Producto",
    )
    file = models.FileField(
        upload_to="products/videos/",
        storage=_video_storage,
        verbose_name="Archivo de video",
        help_text="Formatos soportados: .mp4, .webm. Se reproduce automáticamente en la galería.",
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Menor número = aparece primero.",
    )

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "Video personalizado"
        verbose_name_plural = "Videos personalizados"

    def __str__(self):
        return f"{self.product.name} – video {self.order}"


class ProductReview(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Producto",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="product_reviews",
        verbose_name="Usuario",
        help_text="Vacío en reseñas dejadas sin cuenta desde el enlace del pedido.",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviews",
        verbose_name="Pedido",
        help_text="Pedido entregado que respalda la reseña (compra verificada).",
    )
    author_name = models.CharField(max_length=80, blank=True, verbose_name="Nombre visible")
    author_city = models.CharField(max_length=80, blank=True, verbose_name="Ciudad")
    score = models.PositiveSmallIntegerField(
        verbose_name="Puntuación",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, verbose_name="Comentario")
    is_published = models.BooleanField(
        default=True,
        verbose_name="Publicada",
        help_text="Solo las publicadas cuentan en el promedio de la tienda.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizada")

    class Meta:
        verbose_name = "Reseña de producto"
        verbose_name_plural = "Reseñas de productos"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                name="catalog_productreview_unique_user_product",
            ),
            models.UniqueConstraint(
                fields=["product", "order"],
                condition=models.Q(order__isnull=False),
                name="catalog_productreview_unique_order_product",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "is_published"]),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.score}/5 ({self.user or self.author_name or 'cliente'})"

    @property
    def display_author(self) -> str:
        """Nombre de pila + inicial del apellido ("Laura M."), nunca completo."""
        if self.author_name:
            return self.author_name
        if self.user_id:
            first = (self.user.first_name or "").strip()
            last = (self.user.last_name or "").strip()
            if first:
                return f"{first} {last[:1]}." if last else first
        return "Cliente"

    @property
    def is_verified_purchase(self) -> bool:
        return bool(self.order_id)


class HeroBanner(models.Model):
    title = models.CharField(max_length=200, verbose_name="Título")
    subtitle = models.CharField(max_length=400, blank=True, verbose_name="Subtítulo")
    cta_text = models.CharField(max_length=100, blank=True, verbose_name="Texto del botón")
    cta_url = models.CharField(max_length=500, blank=True, verbose_name="URL del botón")
    image = models.ImageField(
        upload_to="hero/images/",
        blank=True,
        null=True,
        verbose_name="Imagen",
        help_text="JPG, PNG, WebP. Recomendado: 1400 × 530 px (proporción 21:8).",
    )
    video_file = models.FileField(
        upload_to="hero/videos/",
        blank=True,
        null=True,
        verbose_name="Video (archivo MP4)",
        help_text="Sube un .mp4. Se reproduce en silencio y en bucle automático.",
    )
    video_url = models.URLField(
        blank=True,
        verbose_name="Video (URL externa)",
        help_text="URL directa a un .mp4, o enlace de YouTube / Vimeo para embed.",
    )
    overlay_opacity = models.PositiveSmallIntegerField(
        default=50,
        verbose_name="Opacidad del overlay (%)",
        help_text="0 = sin overlay, 100 = negro sólido. Recomendado: 40-60 para texto legible.",
        validators=[MaxValueValidator(100)],
    )
    OBJECT_POSITION_CHOICES = [
        ("center center", "Centro"),
        ("center top",    "Arriba"),
        ("center bottom", "Abajo"),
        ("left center",   "Izquierda"),
        ("right center",  "Derecha"),
        ("left top",      "Izquierda-Arriba"),
        ("right top",     "Derecha-Arriba"),
        ("left bottom",   "Izquierda-Abajo"),
        ("right bottom",  "Derecha-Abajo"),
    ]
    object_position = models.CharField(
        max_length=30,
        choices=OBJECT_POSITION_CHOICES,
        default="center center",
        verbose_name="Posición de la imagen",
        help_text="Controla qué parte de la imagen queda visible cuando se recorta.",
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Orden")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Banner hero"
        verbose_name_plural = "Banners hero"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    @property
    def media_type(self):
        if self.video_file:
            return "video_file"
        if self.video_url:
            return "video_url"
        return "image"

    @property
    def is_youtube(self):
        url = self.video_url or ""
        return "youtube.com" in url or "youtu.be" in url

    @property
    def youtube_embed_url(self):
        import re
        url = self.video_url or ""
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        if match:
            vid = match.group(1)
            return (
                f"https://www.youtube.com/embed/{vid}"
                f"?autoplay=1&mute=1&loop=1&playlist={vid}&controls=0&showinfo=0&rel=0"
            )
        return url


class ShippingExperimentEvent(models.Model):
    """Instrumentación del experimento 'envío real + razón' — SOLO para
    productos Product.needs_combo (ver arriba). Permite comparar, por
    producto: cuántas veces se mostró el cargo de envío real, cuántas
    terminaron en compra pagándolo, y cuántas el comprador prefirió el
    combo sugerido en su lugar. Ver catalog/services/shipping_experiment.py."""

    EVENT_SHOWN = "shown"
    EVENT_PURCHASED_SURCHARGE = "purchased_surcharge"
    EVENT_CHOSE_COMBO = "chose_combo"
    EVENT_CHOICES = [
        (EVENT_SHOWN, "Mostrado"),
        (EVENT_PURCHASED_SURCHARGE, "Compró pagando el envío real"),
        (EVENT_CHOSE_COMBO, "Prefirió el combo sugerido"),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="shipping_experiment_events",
        verbose_name="Producto",
    )
    event_type = models.CharField(max_length=24, choices=EVENT_CHOICES, verbose_name="Evento")
    city = models.CharField(max_length=200, blank=True, verbose_name="Ciudad")
    zone = models.CharField(max_length=1, blank=True, verbose_name="Zona")
    shipping_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Cargo de envío mostrado/pagado",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shipping_experiment_events",
        verbose_name="Orden",
    )
    session_key = models.CharField(max_length=40, blank=True, verbose_name="Sesión")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "Evento de experimento de envío"
        verbose_name_plural = "Eventos de experimento de envío"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "event_type"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.product.name} ({self.created_at:%Y-%m-%d})"


class StoreSettings(models.Model):
    """Datos de la tienda editables desde el admin (una sola fila). Un campo
    vacío usa el valor de settings/variables de entorno (STORE_*), así nada
    se rompe antes de llenarlo. Ver catalog/store_config.py."""

    name = models.CharField("Nombre comercial", max_length=120, blank=True)
    legal_name = models.CharField(
        "Razón social", max_length=200, blank=True,
        help_text="Tal como aparece en el RUT / Cámara de Comercio. Si no hay sociedad, el nombre de la persona.",
    )
    nit = models.CharField("RFC", max_length=40, blank=True, help_text="12 o 13 caracteres, p. ej. PST250101AB1. Vacío = no se muestra.")
    address = models.CharField("Dirección", max_length=200, blank=True, help_text="Vacío = solo se muestra la ciudad.")
    city = models.CharField("Ciudad", max_length=120, blank=True, help_text="P. ej. Guadalajara, Jalisco.")
    email = models.EmailField("Correo de atención", blank=True)
    whatsapp = models.CharField(
        "WhatsApp (solo dígitos, con 57)", max_length=20, blank=True, help_text="P. ej. 573013036922. Se usa en los enlaces wa.me.",
    )
    whatsapp_display = models.CharField("WhatsApp como se muestra", max_length=40, blank=True, help_text="P. ej. +52 55 1234 5678.")
    support_hours = models.CharField(
        "Horario de atención", max_length=120, blank=True,
        help_text='P. ej. "Lunes a sábado, 8 a. m. a 6 p. m.". Vacío = no se promete horario.',
    )
    instagram = models.CharField("Usuario de Instagram", max_length=60, blank=True, help_text="Sin @. Vacío = no se muestra.")
    whatsapp_channel_url = models.URLField(
        "Canal de WhatsApp", blank=True,
        help_text="Enlace real del canal (whatsapp.com/channel/…). Vacío = el inicio invita a escribir por WhatsApp.",
    )
    dispatch_cutoff_hour = models.PositiveSmallIntegerField(
        "Hora de corte de despacho", null=True, blank=True, validators=[MaxValueValidator(23)],
        help_text="0-23, hora de Bogotá. Pedidos de lunes a viernes antes de esta hora salen el mismo día.",
    )
    trust_min_delivered = models.PositiveIntegerField(
        "Mínimo de entregas para mostrar la cifra", null=True, blank=True,
        help_text='El contador "N pedidos entregados" aparece desde este número.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de la tienda"
        verbose_name_plural = "Configuración de la tienda"

    def __str__(self):
        return "Configuración de la tienda"

    def save(self, *args, **kwargs):
        self.pk = 1  # una sola fila
        super().save(*args, **kwargs)
        from django.core.cache import cache

        from .store_config import CACHE_KEYS

        cache.delete_many(CACHE_KEYS)


class FeedSnapshot(models.Model):
    """Última versión buena de un archivo generado (hoy: el feed de Google
    Merchant), comprimida con gzip. El disco del contenedor se borra en cada
    despliegue o reinicio; sin esta copia, el feed respondía error mientras se
    volvía a generar y Merchant Center podía fallar la descarga del día."""

    name = models.CharField(max_length=60, primary_key=True)
    content_gz = models.BinaryField()
    item_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()

    class Meta:
        verbose_name = "Copia de feed"
        verbose_name_plural = "Copias de feeds"

    def __str__(self):
        return f"{self.name} ({self.item_count} productos, {self.created_at:%Y-%m-%d %H:%M})"


class Collection(models.Model):
    """Colección por intención de búsqueda dentro de una categoría:
    /categoria/cocina/organizadores-de-cocina/. Página propia con H1, texto,
    preguntas frecuentes y los productos cuyo nombre coincide con
    include_terms (ver catalog/services/collections.py). Son URLs nuevas: no
    cambian ni reemplazan ninguna página existente."""

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="collections", verbose_name="Categoría")
    slug = models.SlugField(max_length=80, verbose_name="URL")
    name = models.CharField(max_length=90, verbose_name="Nombre (H1)")
    seo_title = models.CharField(
        max_length=70, blank=True, verbose_name="Título SEO",
        help_text="Vacío = «Nombre con pago contra entrega | Pegasus Store».",
    )
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="Meta descripción")
    intro = models.TextField(blank=True, verbose_name="Texto de introducción", help_text="Párrafos separados por una línea en blanco.")
    faq = models.JSONField(default=list, blank=True, verbose_name="Preguntas frecuentes", help_text='Lista de {"q": "…", "a": "…"}.')
    include_terms = models.TextField(
        verbose_name="Términos que incluyen",
        help_text="Uno por línea, sin tildes. Entra el producto cuyo nombre contiene alguno como palabras completas (también en plural).",
    )
    exclude_terms = models.TextField(blank=True, verbose_name="Términos que excluyen", help_text="Uno por línea.")
    is_published = models.BooleanField(default=False, verbose_name="Publicada")
    position = models.PositiveSmallIntegerField(default=100, verbose_name="Orden")
    products = models.ManyToManyField("Product", blank=True, related_name="collections", verbose_name="Productos")
    product_count = models.PositiveIntegerField(default=0, verbose_name="Productos")
    refreshed_at = models.DateTimeField(null=True, blank=True, verbose_name="Productos recalculados")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Colección"
        verbose_name_plural = "Colecciones"
        ordering = ["category__name", "position", "name"]
        constraints = [
            models.UniqueConstraint(fields=["category", "slug"], name="catalog_collection_unique_category_slug"),
        ]

    def __str__(self):
        return f"{self.category.name} › {self.name}"

    def get_absolute_url(self):
        from .seo import category_slug

        return f"/categoria/{category_slug(self.category.dropi_id)}/{self.slug}/"

    @property
    def intro_paragraphs(self) -> list[str]:
        return [p.strip() for p in (self.intro or "").split("\n\n") if p.strip()]
