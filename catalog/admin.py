from django.contrib import admin, messages
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from dropi_client import DropiClient, DropiAPIError

from .models import (
    Category, HeroBanner, Product, ProductImage, ProductReview, ProductVideo,
    Collection, ShippingExperimentEvent, StoreSettings,
)
from .services.dropi_import import parse_images as _parse_images, upsert_product as _upsert_product_svc

CDN_BASE = "https://d39ru7awumhhs2.cloudfront.net/"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "dropi_id", "parent", "thumb_preview")
    list_filter = ("parent",)
    search_fields = ("name",)
    readonly_fields = ("thumb_preview",)
    fields = ("dropi_id", "name", "parent", "image", "thumb_preview")

    def thumb_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:60px;height:60px;object-fit:cover;border-radius:50%;border:2px solid #C9A84C;" />',
                obj.image.url,
            )
        return mark_safe('<span style="color:#9ca3af">Sin imagen</span>')
    thumb_preview.short_description = "Vista previa"


def _upsert_product(raw: dict) -> Product:
    """Thin wrapper kept for backwards compatibility with admin views."""
    product, _ = _upsert_product_svc(raw)
    return product


@admin.action(description="🔄 Sincronizar productos desde Dropi")
def sync_from_dropi(modeladmin, request, queryset):
    client = DropiClient()
    page = 0
    page_size = 50
    total_created = 0
    total_updated = 0

    try:
        while True:
            resp = client.get_products(page=page, page_size=page_size)
            objects = resp.get("objects") or []
            if isinstance(objects, dict):
                products_list = objects.get("products") or objects.get("data") or []
            elif isinstance(objects, list):
                products_list = objects
            else:
                products_list = []

            if not products_list:
                break

            for raw in products_list:
                exists = Product.objects.filter(dropi_id=raw.get("id")).exists()
                _upsert_product(raw)
                if exists:
                    total_updated += 1
                else:
                    total_created += 1

            page += 1
            if len(products_list) < page_size:
                break

    except DropiAPIError as exc:
        messages.error(request, f"Error al comunicarse con Dropi: {exc}")
        return

    messages.success(
        request,
        f"Sync completada: {total_created} productos nuevos, {total_updated} actualizados.",
    )


@admin.action(description="🔗 Registrar en Dropi (import list)")
def register_with_dropi(modeladmin, request, queryset):
    """Register selected products in Dropi's import list so orders work correctly."""
    client = DropiClient()
    ok = 0
    failed = 0
    for product in queryset:
        try:
            client.mark_imported(product.dropi_id, product.pk, product.slug)
            ok += 1
        except DropiAPIError:
            failed += 1
    if ok:
        messages.success(request, f"{ok} producto(s) registrado(s) en Dropi correctamente.")
    if failed:
        messages.warning(request, f"{failed} producto(s) no pudieron registrarse en Dropi.")


@admin.action(description="✅ Activar productos seleccionados")
def activate_products(modeladmin, request, queryset):
    count = queryset.update(is_active=True)
    messages.success(request, f"{count} producto(s) activado(s).")


@admin.action(description="❌ Desactivar productos seleccionados")
def deactivate_products(modeladmin, request, queryset):
    count = queryset.update(is_active=False)
    messages.success(request, f"{count} producto(s) desactivado(s).")

@admin.action(description="\U0001f6ab Marcar imagen irrelevante (ocultar)")
def flag_image_irrelevant(modeladmin, request, queryset):
    count = queryset.update(image_flagged=True, is_active=False)
    messages.warning(request, f"{count} producto(s) marcado(s) con imagen irrelevante y ocultado(s) del cat\u00e1logo.")


@admin.action(description="\U0001f5bc\ufe0f Quitar bandera de imagen")
def unflag_image(modeladmin, request, queryset):
    count = queryset.update(image_flagged=False)
    messages.success(request, f"Bandera de imagen quitada a {count} producto(s). Activa manualmente para publicar.")

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "order", "image_preview")
    readonly_fields = ("image_preview",)
    ordering = ("order",)

    @admin.display(description="Vista previa")
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="height:80px;width:80px;object-fit:cover;border-radius:6px;border:1px solid #ddd;" />',
                obj.image.url,
            )
        return "—"


class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 1
    fields = ("file", "order", "video_preview")
    readonly_fields = ("video_preview",)
    ordering = ("order",)

    @admin.display(description="Vista previa")
    def video_preview(self, obj):
        if obj.pk and obj.file:
            try:
                url = obj.file.url
                return mark_safe(
                    f'<video src="{url}" style="height:80px;width:120px;border-radius:6px;border:1px solid #ddd;" '
                    f'muted preload="metadata"></video>'
                )
            except Exception:
                return "—"
        return "—"

    def save_formset(self, request, form, formset, change):
        """Use RawMediaCloudinaryStorage for video files so Cloudinary accepts mp4/webm."""
        # NOTE: storage is now set directly on ProductVideo.file via _video_storage callable.
        # This method just delegates to default behavior.
        formset.save()


class IsProfitableFilter(admin.SimpleListFilter):
    """Filtra por Product.profitability_status — no es un campo de DB, así
    que se evalúa en Python sobre pk__in. Ver catalog/models.py para las
    3 reglas (techo de envío / margen pesos+% / combo)."""
    title = "rentabilidad neta"
    parameter_name = "profitability"

    def lookups(self, request, model_admin):
        return (
            ("profitable", "Rentable"),
            ("needs_combo", "Necesita combo (sobre el techo de envío)"),
            ("unprofitable", "Sin margen (bajo el techo)"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value not in ("profitable", "needs_combo", "unprofitable"):
            return queryset
        ids = [
            p.pk for p in queryset.only("id", "price", "cost")
            if p.profitability_status == value
        ]
        return queryset.filter(pk__in=ids)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "thumbnail_preview",
        "name",
        "category",
        "category_confidence",
        "category_locked",
        "cost",
        "price",
        "profit_display",
        "is_profitable_display",
        "stock",
        "rank_score",
        "is_active",
        "is_featured",
        "is_new_arrival",
        "image_flagged",
        "rating_average",
        "rating_count",
        "view_links",
    )
    list_editable = ("price", "cost", "stock", "is_active", "is_featured", "is_new_arrival", "category_locked", "image_flagged")
    list_filter = (
        "is_active", "inactive_reason", IsProfitableFilter, "pricing_status", "price_locked",
        "is_featured", "is_new_arrival", "image_flagged", "category_locked", "seo_exclusion", "category",
    )
    search_fields = ("name", "dropi_id", "dropi_category_name")
    readonly_fields = (
        "dropi_id", "dropi_category_id", "dropi_category_name", "images", "variants",
        "last_synced", "slug", "image_gallery_preview",
        "suggested_price", "pricing_status", "rank_score", "inactive_reason", "gallery_synced_at",
        "category_confidence", "category_reason", "rating_average", "rating_count",
        "buy_now_link_display", "profitability_detail_display", "combo_candidates_display",
        "shipping_experiment_summary_display",
    )
    inlines = [ProductImageInline, ProductVideoInline]
    actions = [sync_from_dropi, register_with_dropi, activate_products, deactivate_products, flag_image_irrelevant, unflag_image]
    change_list_template = "admin/catalog/product_change_list.html"
    list_per_page = 25

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "sync-dropi/",
                self.admin_site.admin_view(self.sync_dropi_view),
                name="catalog_sync_dropi",
            ),
            path(
                "explorar-dropi/",
                self.admin_site.admin_view(self.explorar_dropi_view),
                name="catalog_explorar_dropi",
            ),
            path(
                "importar-dropi/<int:dropi_id>/",
                self.admin_site.admin_view(self.importar_producto_view),
                name="catalog_importar_producto",
            ),
            path(
                "importar-url/",
                self.admin_site.admin_view(self.importar_url_view),
                name="catalog_importar_url",
            ),
            path(
                "importar-manual/",
                self.admin_site.admin_view(self.importar_manual_view),
                name="catalog_importar_manual",
            ),
        ]
        return custom + urls

    def sync_dropi_view(self, request):
        """Direct sync view — no row selection needed."""
        client = DropiClient()
        page = 0
        page_size = 50
        total_created = 0
        total_updated = 0

        try:
            while True:
                resp = client.get_products(page=page, page_size=page_size)
                objects = resp.get("objects") or []
                if isinstance(objects, dict):
                    products_list = objects.get("products") or objects.get("data") or []
                elif isinstance(objects, list):
                    products_list = objects
                else:
                    products_list = []

                if not products_list:
                    break

                for raw in products_list:
                    exists = Product.objects.filter(dropi_id=raw.get("id")).exists()
                    _upsert_product(raw)
                    if exists:
                        total_updated += 1
                    else:
                        total_created += 1

                page += 1
                if len(products_list) < page_size:
                    break

        except DropiAPIError as exc:
            messages.error(request, f"Error al comunicarse con Dropi: {exc}")
            return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

        messages.success(
            request,
            f"✅ Sync completada: {total_created} productos nuevos, {total_updated} actualizados.",
        )
        return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

    def importar_url_view(self, request):
        """Import a product from a Dropi product URL pasted by the admin."""
        import re

        if request.method != "POST":
            return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

        url = request.POST.get("dropi_url", "").strip()

        # Extract numeric product ID from URL patterns like:
        # https://app.dropi.co/dashboard/product-details/547521/termo-dispensador...
        # https://app.dropi.co/dashboard/supplier/products/detail/547521
        match = re.search(r"/product[s\-details/]*?/(\d+)", url)
        if not match:
            # Fallback: any sequence of 4+ digits in the URL
            match = re.search(r"/(\d{4,})", url)

        if not match:
            messages.error(
                request,
                "No se pudo extraer el ID del producto de esa URL. "
                "Asegúrate de pegar el enlace completo de Dropi.",
            )
            return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

        dropi_id = int(match.group(1))
        client = DropiClient()
        try:
            resp = client.get_product(dropi_id)
            raw = resp.get("objects") or {}
            # Fallback: if direct GET fails (401 = product not in this integration's catalog)
            # try fetching via the product list endpoint with the ID as keyword
            if not raw:
                search_resp = client.get_products(page=0, page_size=1, keywords=str(dropi_id))
                objects = search_resp.get("objects") or []
                if isinstance(objects, dict):
                    objects = objects.get("products") or objects.get("data") or []
                raw = next((p for p in objects if p.get("id") == dropi_id), {})
        except DropiAPIError as exc:
            err_str = str(exc)
            if "401" in err_str:
                # Product might not be in this integration - try keyword search
                try:
                    search_resp = client.get_products(page=0, page_size=5, keywords=str(dropi_id))
                    objects = search_resp.get("objects") or []
                    if isinstance(objects, dict):
                        objects = objects.get("products") or objects.get("data") or []
                    raw = next((p for p in objects if p.get("id") == dropi_id), None)
                    if not raw:
                        messages.warning(
                            request,
                            mark_safe(
                                f"API de Dropi no disponible para el ID {dropi_id}. "
                                f'<a href="{reverse("admin:catalog_importar_manual")}?dropi_url={url}" '
                                f'style="text-decoration:underline;font-weight:bold;">Agregar manualmente →</a>'
                            ),
                        )
                        return HttpResponseRedirect(reverse("admin:catalog_importar_manual") + f"?dropi_url={url}")
                    resp = {"objects": raw}
                except DropiAPIError as exc2:
                    messages.error(request, f"Error al conectar con Dropi: {exc2}")
                    return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))
            else:
                messages.error(request, f"Error al conectar con Dropi: {exc}")
                return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

        if not raw:
            messages.error(request, f"Dropi no devolvió datos para el ID {dropi_id}. Verifica el enlace.")
            return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

        try:
            product = _upsert_product(raw)
            try:
                client.mark_imported(product.dropi_id, product.pk, product.slug)
            except DropiAPIError:
                pass  # Non-fatal
            edit_url = reverse("admin:catalog_product_change", args=[product.pk])
            messages.success(
                request,
                mark_safe(
                    f'✅ <strong>{product.name}</strong> importado correctamente. '
                    f'<a href="{edit_url}" style="text-decoration:underline;">Configura el precio y actívalo →</a>'
                ),
            )
        except Exception as exc:
            messages.error(request, f"Error al guardar el producto: {exc}")

        return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

    def importar_manual_view(self, request):
        """Manual product creation form — no Dropi API required."""
        import re as _re
        from django.shortcuts import render
        from .models import Category

        if request.method == "POST":
            dropi_url = request.POST.get("dropi_url", "").strip()
            dropi_id_raw = request.POST.get("dropi_id", "").strip()
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "").strip()
            price = request.POST.get("price", "").strip()
            cost = request.POST.get("cost", "0").strip()
            stock = request.POST.get("stock", "0").strip()
            supplier_id = request.POST.get("supplier_id", "0").strip()
            category_id = request.POST.get("category", "").strip()
            image_urls_raw = request.POST.get("image_urls", "").strip()
            video_url_manual = request.POST.get("video_url", "").strip()

            # Derive dropi_id from URL or explicit field
            dropi_id = None
            if dropi_id_raw and dropi_id_raw.isdigit():
                dropi_id = int(dropi_id_raw)
            elif dropi_url:
                m = _re.search(r"/product[s\-details/]*?/(\d+)", dropi_url)
                if not m:
                    m = _re.search(r"/(\d{4,})", dropi_url)
                if m:
                    dropi_id = int(m.group(1))

            errors = []
            if not dropi_id:
                errors.append("ID de Dropi inválido o URL incorrecta.")
            if not name:
                errors.append("El nombre es obligatorio.")
            if not price or not price.replace(".", "").replace(",", "").isdigit():
                errors.append("Precio inválido.")

            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                from decimal import Decimal, InvalidOperation
                try:
                    price_dec = Decimal(price.replace(",", ""))
                    cost_dec = Decimal(cost.replace(",", "") or "0")
                    stock_int = int(stock or "0")
                    supplier_int = int(supplier_id or "0")
                except (InvalidOperation, ValueError):
                    messages.error(request, "Precio, costo o stock inválido.")
                    return HttpResponseRedirect(reverse("admin:catalog_importar_manual"))

                # Parse image URLs (one per line or comma-separated)
                images = []
                for line in _re.split(r"[\n,]+", image_urls_raw):
                    url = line.strip()
                    if url.startswith("http"):
                        images.append({"url": url})

                category_obj = None
                if category_id:
                    try:
                        category_obj = Category.objects.get(pk=int(category_id))
                    except (Category.DoesNotExist, ValueError):
                        pass

                # Check duplicate
                existing = Product.objects.filter(dropi_id=dropi_id).first()
                if existing:
                    messages.warning(
                        request,
                        mark_safe(
                            f'Producto con ID Dropi {dropi_id} ya existe: <strong>{existing.name}</strong>. '
                            f'<a href="{reverse("admin:catalog_product_change", args=[existing.pk])}">Editar →</a>'
                        ),
                    )
                    return HttpResponseRedirect(reverse("admin:catalog_importar_manual"))

                product = Product(
                    dropi_id=dropi_id,
                    name=name,
                    description=description,
                    price=price_dec,
                    cost=cost_dec,
                    stock=stock_int,
                    supplier_id=supplier_int,
                    images=images,
                    is_active=False,
                    category=category_obj,
                    video_url=video_url_manual,
                )
                # Handle video file upload
                video_file = request.FILES.get("video_file")
                if video_file:
                    product.video_file = video_file
                product.save()

                # Handle image file uploads (creates ProductImage instances)
                image_files = request.FILES.getlist("image_files")
                for i, img_file in enumerate(image_files):
                    from .models import ProductImage
                    ProductImage.objects.create(product=product, image=img_file, order=i)

                # Try to register in Dropi import list (non-fatal)
                try:
                    from dropi_client import DropiClient, DropiAPIError as _DAE
                    DropiClient().mark_imported(product.dropi_id, product.pk, product.slug)
                except Exception:
                    pass

                edit_url = reverse("admin:catalog_product_change", args=[product.pk])
                messages.success(
                    request,
                    mark_safe(
                        f'✅ <strong>{product.name}</strong> creado manualmente (ID Dropi: {dropi_id}). '
                        f'<a href="{edit_url}">Configurar y activar →</a>'
                    ),
                )
                return HttpResponseRedirect(edit_url)

        # GET — show form
        # Pre-fill dropi_id from URL param if present
        prefill_url = request.GET.get("dropi_url", "")
        prefill_id = ""
        if prefill_url:
            import re as _re2
            m = _re2.search(r"/product[s\-details/]*?/(\d+)", prefill_url)
            if not m:
                m = _re2.search(r"/(\d{4,})", prefill_url)
            if m:
                prefill_id = m.group(1)

        categories = Category.objects.order_by("name")
        context = {
            **self.admin_site.each_context(request),
            "title": "Agregar producto manualmente",
            "opts": self.model._meta,
            "categories": categories,
            "prefill_url": prefill_url,
            "prefill_id": prefill_id,
        }
        return render(request, "admin/catalog/importar_manual.html", context)

    def explorar_dropi_view(self, request):
        """Browse Dropi catalog page by page and pick which products to import."""
        from django.shortcuts import render

        client = DropiClient()
        page = int(request.GET.get("page", 0))
        page_size = 20
        search = request.GET.get("q", "").strip()

        try:
            resp = client.get_products(page=page, page_size=page_size, keywords=search or None)
            objects = resp.get("objects") or []
        except DropiAPIError as exc:
            messages.error(request, f"Error al conectar con Dropi: {exc}")
            objects = []

        # Mark which products are already imported
        dropi_ids_in_page = [p.get("id") for p in objects if p.get("id")]
        already_imported = set(
            Product.objects.filter(dropi_id__in=dropi_ids_in_page).values_list("dropi_id", flat=True)
        )

        productos = []
        for raw in objects:
            dropi_id = raw.get("id")
            imgs = _parse_images(raw)
            main_img = imgs[0]["url"] if imgs else ""
            name = (raw.get("name") or "").strip()
            cost = raw.get("sale_price") or 0
            suggested = raw.get("suggested_price") or cost
            stock = sum(
                wh.get("stock", 0) for wh in (raw.get("warehouse_product") or [])
                if isinstance(wh, dict)
            )
            cats = raw.get("categories") or []
            cat_name = cats[0].get("name", "") if cats else ""
            productos.append({
                "dropi_id": dropi_id,
                "name": name or "(sin nombre)",
                "main_img": main_img,
                "cost": cost,
                "suggested": suggested,
                "stock": stock,
                "category": cat_name,
                "imported": dropi_id in already_imported,
            })

        context = {
            **self.admin_site.each_context(request),
            "title": "Explorar catálogo Dropi",
            "productos": productos,
            "page": page,
            "prev_page": page - 1 if page > 0 else None,
            "next_page": page + 1 if len(objects) == page_size else None,
            "search": search,
            "opts": self.model._meta,
        }
        return render(request, "admin/catalog/explorar_dropi.html", context)

    def importar_producto_view(self, request, dropi_id):
        """Import a single product by its Dropi ID."""
        if request.method != "POST":
            return HttpResponseRedirect(reverse("admin:catalog_explorar_dropi"))

        client = DropiClient()
        try:
            resp = client.get_product(dropi_id)
            raw = resp.get("objects") or {}
            if not raw:
                messages.error(request, f"No se encontró el producto {dropi_id} en Dropi.")
            else:
                product = _upsert_product(raw)
                # Register in Dropi's import list so orders can reference by local PK
                try:
                    client.mark_imported(product.dropi_id, product.pk, product.slug)
                except DropiAPIError:
                    pass  # Non-fatal — product is saved locally, order will fail until re-registered
                messages.success(
                    request,
                    f'✅ "{product.name}" importado. '
                    f'<a href="{reverse("admin:catalog_product_change", args=[product.pk])}">Configurar precio y activar →</a>',
                )
        except DropiAPIError as exc:
            messages.error(request, f"Error al importar: {exc}")

        # Return to the same explorer page
        referer = request.META.get("HTTP_REFERER", "")
        if "explorar-dropi" in referer:
            return HttpResponseRedirect(referer)
        return HttpResponseRedirect(reverse("admin:catalog_explorar_dropi"))

    @admin.display(description="Imagen")
    def thumbnail_preview(self, obj):
        img = obj.main_image
        if img:
            return format_html(
                '<img src="{}" style="height:60px;width:60px;object-fit:cover;border-radius:6px;border:1px solid #ddd;" />',
                img,
            )
        return mark_safe('<span style="color:#ccc;font-size:22px;">📦</span>')

    @admin.display(description="Galería")
    def image_gallery_preview(self, obj):
        imgs_html = ""
        # Custom images first
        for ci in obj.custom_images.all():
            imgs_html += (
                f'<img src="{ci.image.url}" '
                f'style="height:100px;width:100px;object-fit:cover;border-radius:6px;margin:4px;border:2px solid #6d28d9;" '
                f'title="Personalizada (orden {ci.order})" />'
            )
        # Dropi images (background)
        for img in (obj.images or []):
            url = img.get("url") if isinstance(img, dict) else ""
            if url:
                imgs_html += (
                    f'<img src="{url}" '
                    f'style="height:100px;width:100px;object-fit:cover;border-radius:6px;margin:4px;border:1px solid #ddd;opacity:0.6;" '
                    f'title="Dropi (solo lectura)" />'
                )
        if not imgs_html:
            return "Sin imágenes"
        legend = (
            '<p style="font-size:11px;color:#6b7280;margin:4px 0 8px;">' 
            '<span style="border:2px solid #6d28d9;padding:1px 4px;border-radius:3px;">■</span> Personalizadas '
            '&nbsp;&nbsp;<span style="border:1px solid #ddd;padding:1px 4px;border-radius:3px;opacity:0.6;">■</span> Dropi</p>'
        )
        return mark_safe(f'<div style="display:flex;flex-wrap:wrap;gap:4px;">{imgs_html}</div>{legend}')

    @admin.display(description="Ver")
    def view_links(self, obj):
        links = []
        if obj.slug:
            links.append(
                f'<a href="/producto/{obj.slug}/" target="_blank" '
                f'style="background:#6d28d9;color:white;padding:3px 8px;border-radius:4px;font-size:11px;text-decoration:none;">🛍 Tienda</a>'
            )
        if obj.pk and obj.is_active:
            buy_url = self._buy_now_url(obj.pk)
            links.append(
                f'<a href="{buy_url}" target="_blank" rel="noopener" '
                f'style="background:#059669;color:white;padding:3px 8px;border-radius:4px;font-size:11px;text-decoration:none;">🛒 Comprar</a>'
            )
        links.append(
            f'<a href="https://app.dropi.co/dashboard/supplier/products" target="_blank" '
            f'style="background:#f59e0b;color:white;padding:3px 8px;border-radius:4px;font-size:11px;text-decoration:none;">Dropi ↗</a>'
        )
        return mark_safe(" ".join(links))

    @staticmethod
    def _buy_now_url(product_id: int) -> str:
        path = reverse("cart:buy_now", kwargs={"product_id": product_id})
        base = getattr(settings, "STORE_SITE_URL", "").strip().rstrip("/")
        return f"{base}{path}" if base else path

    @admin.display(description="Link compra directa")
    def buy_now_link_display(self, obj):
        if not obj.pk:
            return "Guarda el producto para generar el link."
        if not obj.is_active:
            return format_html('<span style="color:#9ca3af;">Producto inactivo — actívalo para usar el link.</span>')
        url = self._buy_now_url(obj.pk)
        return format_html(
            '<input type="text" readonly value="{url}" '
            'style="width:100%;max-width:560px;padding:8px 10px;font-family:monospace;font-size:12px;" '
            'onclick="this.select();document.execCommand(\'copy\');" />'
            '<p style="margin:8px 0 0;font-size:11px;color:#6b7280;">'
            'Clic para seleccionar/copiar. El cliente llega a checkout con este producto en el carrito.'
            '</p>'
            '<p style="margin:4px 0 0;">'
            '<a href="{url}" target="_blank" rel="noopener">Probar link ↗</a>'
            '</p>',
            url=url,
        )

    @admin.display(description="Ganancia")
    def profit_display(self, obj):
        profit = obj.profit
        color = "green" if profit > 0 else "red"
        return format_html('<span style="color:{};font-weight:bold;">${}</span>', color, f"{profit:,.0f}")

    @admin.display(description="Rentable (neto)")
    def is_profitable_display(self, obj):
        status = obj.profitability_status
        net = obj.expected_net_profit
        if status == "profitable":
            color, icon, label = "green", "✓", f"${net:,.0f}"
        elif status == "needs_combo":
            color, icon, label = "#b45309", "⚠", "necesita combo"
        else:
            color, icon, label = "red", "✗", f"${net:,.0f}"
        return format_html(
            '<span style="color:{};font-weight:bold;" '
            'title="Cargo de envío en checkout: ${}. Techo: ${}">{} {}</span>',
            color, f"{obj.shipping_gap:,.0f}", f"{settings.SHIPPING_CEILING:,.0f}", icon, label,
        )

    @admin.display(description="Detalle de rentabilidad")
    def profitability_detail_display(self, obj):
        status_labels = {
            "profitable": ("green", "Rentable"),
            "needs_combo": ("#b45309", "Necesita combo — supera el techo de envío"),
            "unprofitable": ("red", "Sin margen suficiente (bajo el techo)"),
        }
        color, label = status_labels[obj.profitability_status]
        mp = obj.margin_percent
        mp_text = f"{mp:.0%}" if mp is not None else "—"
        return format_html(
            '<p style="font-weight:bold;color:{};margin:0 0 8px;">{}</p>'
            '<ul style="margin:0;padding-left:18px;font-size:12px;color:#374151;">'
            '<li>Margen bruto: ${} ({})</li>'
            '<li>Cargo de envío en checkout (Zona A): ${} — techo configurado: ${}</li>'
            '<li>Ganancia neta esperada (descuenta rechazo COD {:.0%}): ${}</li>'
            '<li>Umbral mínimo neto: ${} — margen % mínimo: {:.0%}</li>'
            '</ul>',
            color, label,
            f"{obj.profit:,.0f}", mp_text,
            f"{obj.shipping_gap:,.0f}", f"{settings.SHIPPING_CEILING:,.0f}",
            settings.COD_REJECTION_RATE, f"{obj.expected_net_profit:,.0f}",
            f"{settings.MIN_NET_PROFIT:,.0f}", settings.MIN_MARGIN_PERCENT,
        )

    @admin.display(description="Candidatos de combo")
    def combo_candidates_display(self, obj):
        if not obj.pk:
            return "Guarda el producto para ver candidatos."
        if not obj.needs_combo:
            return mark_safe(
                '<span style="color:#9ca3af;">No aplica — este producto no supera el techo de envío.</span>'
            )
        from .services.combo_suggestions import suggest_combo_candidates
        candidates = suggest_combo_candidates(obj)
        if not candidates:
            return mark_safe(
                '<span style="color:#b45309;">Sin candidatos en la misma categoría todavía. '
                'Este producto necesita combo pero no hay con qué armarlo — considera ajustar precio o descartarlo.</span>'
            )
        rows = ""
        for c in candidates:
            edit_url = reverse("admin:catalog_product_change", args=[c.pk])
            rows += (
                f'<li style="margin-bottom:6px;">'
                f'<a href="{edit_url}" target="_blank">{c.name}</a> '
                f'— costo ${c.cost:,.0f}, precio ${c.price:,.0f}, margen ${c.profit:,.0f}'
                f'</li>'
            )
        return mark_safe(
            f'<p style="font-size:12px;color:#6b7280;margin:0 0 6px;">'
            f'Candidatos del mismo catálogo (misma categoría, activos, rentables por sí solos, costo similar). '
            f'Tú decides si armas el combo, subes el precio del producto base, o lo descartas — nada se despublica solo.</p>'
            f'<ul style="margin:0;padding-left:18px;">{rows}</ul>'
        )

    @admin.display(description="Experimento envío real + razón")
    def shipping_experiment_summary_display(self, obj):
        if not obj.pk or not obj.needs_combo:
            return mark_safe('<span style="color:#9ca3af;">No aplica — este producto no está en needs_combo.</span>')
        events = obj.shipping_experiment_events.all()
        shown = events.filter(event_type=ShippingExperimentEvent.EVENT_SHOWN).count()
        surcharge = events.filter(event_type=ShippingExperimentEvent.EVENT_PURCHASED_SURCHARGE).count()
        combo = events.filter(event_type=ShippingExperimentEvent.EVENT_CHOSE_COMBO).count()
        link = reverse("admin:catalog_shippingexperimentevent_changelist") + f"?product__id__exact={obj.pk}"
        return format_html(
            'Mostrado: <strong>{}</strong> &nbsp;·&nbsp; '
            'Compró pagando envío real: <strong>{}</strong> &nbsp;·&nbsp; '
            'Prefirió combo: <strong>{}</strong> &nbsp;·&nbsp; '
            '<a href="{}">Ver eventos →</a>',
            shown, surcharge, combo, link,
        )

    fieldsets = (
        (
            "Vista previa de imágenes",
            {"fields": ("image_gallery_preview",)},
        ),
        (
            "Información de Dropi (solo lectura)",
            {
                "fields": (
                    "dropi_id",
                    "dropi_category_id",
                    "dropi_category_name",
                    "supplier_id",
                    "cost",
                    "suggested_price",
                    "stock",
                    "variants",
                    "last_synced",
                    "gallery_synced_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Configuración de tu tienda",
            {
                "fields": (
                    "name",
                    "description",
                    "video_url",
                    "video_file",
                    "category",
                    "category_locked",
                    "category_confidence",
                    "category_reason",
                    "slug",
                    "price",
                    "price_locked",
                    "pricing_status",
                    "rank_score",
                    "is_active",
                    "inactive_reason",
                    "is_featured",
                    "is_new_arrival",
                    "image_flagged",
                )
            },
        ),
        (
            "SEO y contenido único",
            {
                "fields": ("meta_title", "meta_description", "description_unique"),
                "description": (
                    "Generados por `manage.py generate_unique_content` (plantillas, sin IA) — "
                    "editables a mano si quieres ajustar alguno. Vacíos = se usa el fallback "
                    "actual (nombre del producto / descripción cruda de Dropi truncada)."
                ),
            },
        ),
        (
            "Rentabilidad y combo",
            {
                "fields": (
                    "profitability_detail_display",
                    "combo_candidates_display",
                    "shipping_experiment_summary_display",
                ),
                "description": "Ver catalog/models.py (Product.is_profitable) para la fórmula completa.",
            },
        ),
        (
            "Enlaces de venta",
            {
                "fields": ("buy_now_link_display",),
                "description": (
                    "Comparte el link de compra directa (WhatsApp, ads). "
                    "Agrega el producto al carrito y abre checkout. "
                    "Define STORE_SITE_URL en .env para URL absoluta."
                ),
            },
        ),
        (
            "Valoraciones",
            {
                "fields": ("rating_average", "rating_count"),
                "description": "Se actualizan al guardar reseñas publicadas. Vacío = tarjeta usa puntuación provisional.",
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        # video_file storage handled by _video_storage callable on the model field
        # Un precio editado a mano no lo vuelve a pisar reprice_catalog/sync.
        if change and "price" in form.changed_data and "price_locked" not in form.changed_data:
            obj.price_locked = True
        super().save_model(request, obj, form, change)


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "author", "score", "is_published", "short_comment", "created_at")
    list_filter = ("is_published", "score", "created_at")
    search_fields = ("product__name", "user__username", "user__email", "author_name", "author_city", "comment")
    raw_id_fields = ("product", "user", "order")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("product", "user")

    @admin.display(description="Autor")
    def author(self, obj):
        return f"{obj.display_author}{' · pedido #' + str(obj.order_id) if obj.order_id else ''}"

    @admin.display(description="Comentario")
    def short_comment(self, obj):
        if not obj.comment:
            return "—"
        return obj.comment[:60] + ("…" if len(obj.comment) > 60 else "")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from django.core.cache import cache

        from catalog.services.reviews import recalculate_product_rating
        recalculate_product_rating(obj.product_id)
        cache.delete("store_review_summary_v1")

    def delete_model(self, request, obj):
        product_id = obj.product_id
        super().delete_model(request, obj)
        from catalog.services.reviews import recalculate_product_rating
        recalculate_product_rating(product_id)

    def delete_queryset(self, request, queryset):
        product_ids = set(queryset.values_list("product_id", flat=True))
        super().delete_queryset(request, queryset)
        from catalog.services.reviews import recalculate_product_rating
        for pid in product_ids:
            recalculate_product_rating(pid)


@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_active", "media_preview")
    list_editable = ("order", "is_active")
    ordering = ("order",)
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "cta_text", "cta_url", "order", "is_active")}),
        ("Media", {
            "description": "Elige imagen, video subido o URL de video. El video tiene prioridad sobre la imagen.",
            "fields": ("image", "object_position", "video_file", "video_url", "overlay_opacity"),
        }),
    )

    @admin.display(description="Vista previa")
    def media_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:48px;width:auto;border-radius:6px;object-fit:cover;" />',
                obj.image.url,
            )
        if obj.video_file:
            return mark_safe('<span style="color:#6b7280">&#127916; Video subido</span>')
        if obj.video_url:
            short = (obj.video_url[:45] + "…") if len(obj.video_url) > 45 else obj.video_url
            return mark_safe(f'<span style="color:#6b7280">&#128279; {short}</span>')
        return mark_safe('<span style="color:#9ca3af">Sin media</span>')


@admin.register(ShippingExperimentEvent)
class ShippingExperimentEventAdmin(admin.ModelAdmin):
    """Consulta de resultados del experimento 'envío real + razón'
    (needs_combo). Filtra por producto, tipo de evento, zona o rango de
    fecha; el link 'Ver eventos' en cada producto (fieldset 'Rentabilidad y
    combo') llega aquí ya filtrado por ese producto."""
    list_display = ("product", "event_type", "city", "zone", "shipping_amount", "order_link", "created_at")
    list_filter = ("event_type", "zone", "created_at")
    search_fields = ("product__name", "city")
    raw_id_fields = ("product", "order")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("product", "order")

    @admin.display(description="Orden")
    def order_link(self, obj):
        if not obj.order_id:
            return "—"
        url = reverse("admin:orders_order_change", args=[obj.order_id])
        return format_html('<a href="{}">#{}</a>', url, obj.order_id)

    def has_add_permission(self, request):
        # Eventos generados por el flujo de compra/detalle, no manualmente.
        return False


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    """Una sola pantalla: datos legales, contacto y operación que se muestran
    en el footer, Confianza, Quiénes somos, FAQ, fichas y JSON-LD."""

    fieldsets = (
        ("Identidad legal (razón social y RFC: se muestran en el footer y en Confianza)", {
            "fields": ("name", "legal_name", "nit", "address", "city"),
        }),
        ("Contacto", {
            "fields": ("email", "whatsapp", "whatsapp_display", "support_hours", "instagram", "whatsapp_channel_url"),
        }),
        ("Operación", {
            "fields": ("dispatch_cutoff_hour", "trust_min_delivered"),
        }),
        ("Valores en uso ahora", {
            "fields": ("effective_values",),
            "description": "Un campo vacío usa el valor de las variables de entorno (STORE_*).",
        }),
    )
    readonly_fields = ("effective_values",)

    def has_add_permission(self, request):
        return not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj, _ = StoreSettings.objects.get_or_create(pk=1)
        return HttpResponseRedirect(reverse("admin:catalog_storesettings_change", args=[obj.pk]))

    @admin.display(description="En el sitio")
    def effective_values(self, obj):
        from django.utils.html import format_html_join

        from .store_config import store_config

        labels = {f.name: f.verbose_name for f in StoreSettings._meta.fields}
        rows = ((labels.get(k, k), v if v not in ("", None) else "— (no se muestra)") for k, v in store_config().items())
        return format_html('<table>{}</table>', format_html_join("", "<tr><th style='text-align:left;padding-right:16px'>{}</th><td>{}</td></tr>", rows))


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    """Colecciones por tipo de producto (/categoria/x/y/). Al guardar se
    recalculan sus productos según los términos."""

    list_display = ("name", "category", "product_count", "is_published", "position", "page_link", "refreshed_at")
    list_filter = ("is_published", "category")
    list_editable = ("is_published", "position")
    search_fields = ("name", "slug", "include_terms")
    readonly_fields = ("product_count", "refreshed_at", "page_link", "sample_products")
    exclude = ("products",)
    actions = ["recalculate", "publish", "unpublish"]
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "is_published", "position", "page_link")}),
        ("Qué productos entran", {
            "fields": ("include_terms", "exclude_terms", "product_count", "refreshed_at", "sample_products"),
            "description": "Entra el producto cuyo nombre contiene alguno de los términos como palabras completas "
                           "(sin tildes; también en plural). Se recalcula al guardar.",
        }),
        ("Texto de la página", {"fields": ("intro", "faq", "seo_title", "meta_description")}),
    )

    @admin.display(description="Página")
    def page_link(self, obj):
        if not obj.pk:
            return "—"
        return format_html('<a href="{}" target="_blank">{}</a>', obj.get_absolute_url(), obj.get_absolute_url())

    @admin.display(description="Muestra de productos")
    def sample_products(self, obj):
        if not obj.pk:
            return "—"
        from django.utils.html import format_html_join

        names = obj.products.order_by("-rank_score").values_list("name", flat=True)[:15]
        return format_html("<ul>{}</ul>", format_html_join("", "<li>{}</li>", ((n,) for n in names))) if names else "—"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .services.collections import refresh_collections

        refresh_collections([obj])

    @admin.action(description="Recalcular productos")
    def recalculate(self, request, queryset):
        from .services.collections import refresh_collections

        counts = refresh_collections(queryset)
        self.message_user(request, f"{len(counts)} colección(es) recalculadas.")

    @admin.action(description="Publicar")
    def publish(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_published=True)} colección(es) publicadas.")

    @admin.action(description="Pasar a borrador")
    def unpublish(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_published=False)} colección(es) en borrador.")
