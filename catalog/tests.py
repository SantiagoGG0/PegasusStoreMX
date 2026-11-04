from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product, ProductReview, ShippingExperimentEvent
from catalog.navigation import category_filter_dropi_ids, get_nav_categories
from catalog.seo import generate_json_ld, generate_meta_description, generate_og_tags
from catalog.sections import build_home_sections
from catalog.services.categorization import (
    classify_product_text,
    ensure_store_category,
)
from catalog.services.dropi_import import upsert_product
from orders.models import Order

from catalog.services.reviews import recalculate_product_rating, submit_review

User = get_user_model()


class SEOInfrastructureTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="c1", name="Hogar")
        self.product = Product.objects.create(
            dropi_id=999001,
            name="Termo Test SEO",
            description="<p>Descripción <strong>rica</strong> con HTML.</p>",
            category=self.cat,
            price=120000,
            stock=3,
            is_active=True,
            slug="termo-test-seo",
            images=[{"url": "https://example.com/img.jpg"}],
        )

    def test_get_absolute_url(self):
        self.assertEqual(self.product.get_absolute_url(), "/producto/termo-test-seo/")

    def test_meta_description_truncates_and_strips_html(self):
        text = generate_meta_description(self.product)
        self.assertNotIn("<", text)
        self.assertLessEqual(len(text), 160)

    def test_og_tags_absolute_url(self):
        req = self.client.get(self.product.get_absolute_url()).wsgi_request
        tags = dict(generate_og_tags(self.product, req))
        self.assertTrue(tags["og:url"].startswith("http"))
        self.assertEqual(tags["og:image"], "https://example.com/img.jpg")

    def test_json_ld_schema_context(self):
        req = self.client.get(self.product.get_absolute_url()).wsgi_request
        data = generate_json_ld(self.product, req)
        self.assertEqual(data["@context"], "https://schema.org")
        types = {item["@type"]: item for item in data["@graph"]}
        self.assertIn("offers", types["Product"])
        self.assertIn("hasMerchantReturnPolicy", types["Product"]["offers"])
        self.assertRegex(types["Product"]["offers"]["validFrom"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("BreadcrumbList", types)
        self.assertEqual(types["Product"]["brand"]["name"], "Pegasus Store")  # sin marca conocida

    def test_json_ld_brand_from_known_brands(self):
        from catalog.seo import product_brand

        req = self.client.get(self.product.get_absolute_url()).wsgi_request
        self.product.name = "SELVIA AJENJO NUEZ NEGRA"
        product = generate_json_ld(self.product, req)["@graph"][0]
        self.assertEqual(product["brand"]["name"], "Selvia")
        for name, brand in (("CLEARZAL M.P", "Clear Zal"), ("Crema PERFECTX x 2", "Perfectx"),
                            ("Medias Nike Everyday", "Pegasus Store"), ("Clearance zalamera", "Pegasus Store")):
            self.product.name = name
            self.assertEqual(product_brand(self.product), brand, name)

    def test_product_breadcrumb_includes_its_collection(self):
        from catalog.models import Collection

        cat = Category.objects.create(dropi_id="store:hogar", name="Hogar")
        Product.objects.filter(pk=self.product.pk).update(category=cat)
        collection = Collection.objects.create(category=cat, slug="termos", name="Termos y botellas",
                                               include_terms="termo", is_published=True)
        collection.products.add(self.product)
        res = self.client.get(self.product.get_absolute_url())
        self.assertContains(res, 'href="/categoria/hogar/termos/">TERMOS Y BOTELLAS</a>')
        self.assertContains(res, '"name": "Termos y botellas", "item": "http://testserver/categoria/hogar/termos/"')

    def test_robots_txt(self):
        from django.conf import settings

        res = self.client.get("/robots.txt")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Sitemap:", res.content)
        self.assertIn(f"Disallow: /{settings.ADMIN_URL}".encode(), res.content)
        self.assertNotIn(b"Disallow: /admin/", res.content)

    def test_sitemap_xml(self):
        from django.core.cache import cache

        cache.clear()
        res = self.client.get("/sitemap.xml")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"<sitemapindex", res.content)
        self.assertIn(b"/sitemap-productos.xml</loc>", res.content)
        res = self.client.get("/sitemap-productos.xml")
        self.assertIn(b"<urlset", res.content)
        self.assertIn(b"termo-test-seo", res.content)

    def test_product_detail_renders_seo_blocks(self):
        res = self.client.get(self.product.get_absolute_url())
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"application/ld+json", res.content)
        self.assertIn(b"canonical", res.content)


class CatalogHomeTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="hogar-1", name="Hogar")
        Product.objects.create(
            dropi_id=100,
            name="Producto Hogar",
            category=self.cat,
            price=50000,
            stock=10,
            is_active=True,
            slug="producto-hogar",
        )
        Product.objects.create(
            dropi_id=101,
            name="Producto Featured",
            price=99000,
            stock=5,
            is_active=True,
            is_featured=True,
            slug="producto-featured",
        )

    def test_home_shows_catalog_not_tendencias(self):
        # Home is now a curated landing page (hero/categorías/destacados/etc.),
        # not the raw catalog grid — that lives at ?view=all.
        res = self.client.get(reverse("catalog:index"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Lo que más se llevan nuestros clientes")
        self.assertNotContains(res, "Tendencias")

        res_all = self.client.get(reverse("catalog:index"), {"view": "all"})
        self.assertContains(res_all, "Todo el catálogo")

    def test_home_shows_category_filter(self):
        res = self.client.get(reverse("catalog:index"))
        self.assertContains(res, "Hogar")
        res_cat = self.client.get(reverse("catalog:index"), {"category": "hogar-1"})
        self.assertContains(res_cat, "Producto Hogar")
        self.assertNotContains(res_cat, "Producto Featured")

    def test_category_filter_preserves_sort_order(self):
        Product.objects.create(
            dropi_id=102,
            name="Producto Hogar Caro",
            category=self.cat,
            price=80000,
            stock=10,
            is_active=True,
            slug="producto-hogar-caro",
        )

        res = self.client.get(reverse("catalog:index"), {"category": "hogar-1", "sort": "price_desc"})
        html = res.content.decode()

        self.assertLess(html.index("/producto/producto-hogar-caro/"), html.index("/producto/producto-hogar/"))
        self.assertNotIn("Producto Featured", html)

    def test_build_home_sections_only_enabled(self):
        from django.core.paginator import Paginator
        from django.test import RequestFactory

        from catalog.sections import build_home_sections

        rf = RequestFactory()
        request = rf.get("/")
        page_obj = Paginator(Product.objects.filter(is_active=True), 24).get_page(1)
        sections = build_home_sections(
            request,
            page_obj=page_obj,
            categories=Category.objects.all(),
            selected_category=None,
            search_query="",
        )
        ids = [s.id for s in sections]
        # Home (no category/search/view=all) renders the curated rails; the raw
        # listing (catalog_header/catalog_grid) only kicks in once filtered.
        self.assertEqual(
            ids,
            # social_proof solo aparece con reseñas o guías reales; el
            # marquee está apagado.
            ["hero", "featured", "category_tiles", "how_it_works", "faq"],
        )

    def test_live_category_filter_preserves_existing_sort_param(self):
        js = (settings.BASE_DIR / "static" / "js" / "catalog-live-filters.js").read_text(encoding="utf-8")

        self.assertIn('var params = new URLSearchParams(window.location.search);', js)
        self.assertIn('params.set("category", url.searchParams.get("category"));', js)
        self.assertIn('window.applyCatalogSort = applyCatalogSort;', js)


class CategoryNavigationTests(TestCase):
    def test_nav_categories_collapse_alias_roots(self):
        tech_plain = Category.objects.create(dropi_id="tech-plain", name="Tecnologia")
        tech_accent = Category.objects.create(dropi_id="tech-accent", name="Tecnología")
        baby_plural = Category.objects.create(dropi_id="baby-plural", name="Bebes")
        baby_singular = Category.objects.create(dropi_id="baby-singular", name="Bebé")
        for i, category in enumerate((tech_plain, tech_accent, baby_plural, baby_singular), start=1):
            Product.objects.create(
                dropi_id=93000 + i,
                name=f"Producto nav {i}",
                category=category,
                price=10000,
                stock=1,
                is_active=True,
                slug=f"producto-nav-{i}",
            )

        names = [cat.name for cat in get_nav_categories()]

        self.assertEqual(names.count("Tecnología"), 1)
        self.assertEqual(names.count("Bebés"), 1)
        self.assertEqual(sum(1 for name in names if "Tecnolog" in name), 1)

    def test_category_filter_includes_alias_root_categories(self):
        Category.objects.create(dropi_id="tech-plain", name="Tecnologia")
        Category.objects.create(dropi_id="tech-accent", name="Tecnología")

        dropi_ids = set(category_filter_dropi_ids("tech-plain"))

        self.assertEqual(dropi_ids, {"tech-plain", "tech-accent"})


class HeaderAssetTests(TestCase):
    def test_category_bar_is_a_draggable_rail(self):
        # The category pill row is a draggable/momentum-scrolling rail
        # (static/js/rails.js on [data-rail]), not a click-arrow scrollbar —
        # matches the 2026 redesign's rail pattern used across the site.
        template = (settings.BASE_DIR / "templates" / "base.html").read_text(encoding="utf-8")

        self.assertIn('data-rail="cats"', template)
        self.assertIn("cat-pill", template)

    def test_rails_js_implements_drag_and_momentum(self):
        js = (settings.BASE_DIR / "static" / "js" / "rails.js").read_text(encoding="utf-8")

        self.assertIn("data-rail", js)
        self.assertIn("pointerdown", js)
        self.assertIn("data-autoscroll", js)

    def test_city_modal_removed_from_layout(self):
        template = (settings.BASE_DIR / "templates" / "base.html").read_text(encoding="utf-8")

        self.assertNotIn('id="city-modal"', template)
        self.assertNotIn("openCityModal", template)
        self.assertNotIn("¿Dónde te enviamos?", template)


class ProductDetailRecommendationTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="pdp-cat", name="PDP")
        self.product = Product.objects.create(
            dropi_id=94000,
            supplier_id=500,
            name="Producto base PDP",
            category=self.cat,
            price=50000,
            stock=3,
            is_active=True,
            slug="producto-base-pdp",
        )
        self.same_supplier = Product.objects.create(
            dropi_id=94001,
            supplier_id=500,
            name="Mismo proveedor PDP",
            category=self.cat,
            price=51000,
            stock=3,
            is_active=True,
            slug="mismo-proveedor-pdp",
        )
        self.other_supplier = Product.objects.create(
            dropi_id=94002,
            supplier_id=900,
            name="Otro proveedor PDP",
            category=self.cat,
            price=52000,
            stock=3,
            is_active=True,
            slug="otro-proveedor-pdp",
        )

    def test_product_detail_has_no_infinite_catalog(self):
        # La ficha ya no carga "Más productos" con scroll infinito: termina en
        # opiniones y relacionados para no sacar al cliente de la compra.
        response = self.client.get(self.product.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("all_products", response.context)
        self.assertNotContains(response, "pdp-all-grid")

    def test_pdp_more_products_prioritizes_same_supplier_products(self):
        response = self.client.get(
            reverse("catalog:pdp_more_products", kwargs={"exclude_pk": self.product.pk}),
            {"page": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        html = response.json()["html"]
        self.assertLess(html.index("Mismo Proveedor PDP"), html.index("Otro Proveedor PDP"))

    def test_product_detail_prioritizes_fast_checkout_purchase_box(self):
        response = self.client.get(self.product.get_absolute_url())
        html = response.content.decode()

        self.assertIn('class="pdp-purchase-box"', html)
        self.assertIn('class="pdp__delivery-box"', html)
        self.assertLess(html.index('aria-label="Cantidad"'), html.index("Pedir ahora"))
        self.assertLess(html.index("Pedir ahora"), html.index("Agregar al carrito"))
        self.assertLess(html.index("Agregar al carrito"), html.index('class="pdp__delivery-box"'))
        self.assertIn("Pago contra entrega", html)


class HeroSectionTests(TestCase):
    def test_hero_template_is_two_real_product_picks_not_a_carousel(self):
        template = (settings.BASE_DIR / "templates" / "catalog" / "partials" / "section_hero.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("hero-pick", template)
        self.assertNotIn("data-auto-rotate", template)
        self.assertNotIn("setInterval", template)
        self.assertNotIn("hero-counter", template)
        self.assertNotIn("hero-dot", template)

    @override_settings(CATALOG_HOME_SECTIONS=[{"id": "hero"}])
    def test_hero_uses_two_available_catalog_products(self):
        # The hero shows exactly 2 real product picks — confirms it only
        # pulls active, in-stock items.
        cat = Category.objects.create(dropi_id="hero-cat", name="Hero")
        for i in range(6):
            Product.objects.create(
                dropi_id=95000 + i,
                name=f"Producto hero {i}",
                price=10000 + i,
                stock=3,
                category=cat,
                is_active=True,
                slug=f"producto-hero-{i}",
                images=[{"url": f"https://example.com/hero-{i}.jpg"}],
            )
        Product.objects.create(
            dropi_id=96000,
            name="Producto agotado hero",
            price=10000,
            stock=0,
            category=cat,
            is_active=True,
            slug="producto-agotado-hero",
            images=[{"url": "https://example.com/out.jpg"}],
        )

        sections = build_home_sections(RequestFactory().get("/"))

        products = sections[0].context["hero_products"]
        self.assertEqual(len(products), 2)
        self.assertTrue(all(product.is_active for product in products))
        self.assertTrue(all(product.stock > 0 for product in products))


class ProductCategorizationTests(TestCase):
    def test_ventilator_uses_text_over_dropi_vaporizador_category(self):
        result = classify_product_text(
            name="Ventilador portátil recargable USB",
            description="Abanico de mesa para hogar y oficina",
            dropi_category_name="Vaporizadores",
        )

        self.assertEqual(result.category_key, "hogar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_deporte_and_fitness_share_single_category(self):
        result = classify_product_text(
            name="Bandas elásticas fitness para entrenamiento",
            description="Accesorio deportivo para ejercicio en casa",
            dropi_category_name="Deportes",
        )

        self.assertEqual(result.category_key, "deporte_fitness")
        self.assertEqual(result.label, "Deporte y Fitness")

    def test_keyword_matching_uses_words_not_substrings(self):
        result = classify_product_text(
            name="Kit de utensilios cocina x12",
            description="Set completo para preparar alimentos",
            dropi_category_name="Cocina",
        )

        self.assertEqual(result.category_key, "cocina")
        self.assertGreaterEqual(result.confidence, 60)

    def test_airpods_are_technology_not_vehicle(self):
        result = classify_product_text(
            name="Airpods serie 4 bluetooth",
            description="Audífonos inalámbricos",
            dropi_category_name="Electronica",
        )

        self.assertEqual(result.category_key, "tecnologia")
        self.assertGreaterEqual(result.confidence, 60)

    def test_beauty_terms_win_over_generic_toy_words(self):
        result = classify_product_text(
            name="Kit de manicura profesional 12 piezas",
            description="Cortaúñas y cuidado de uñas",
            dropi_category_name="Bebés",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_skin_care_terms_become_beauty(self):
        result = classify_product_text(
            name="Serum retinol ácido hialurónico anti edad",
            description="Rutina facial para acne y cuidado de piel",
            dropi_category_name="Salud",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_weak_generic_match_goes_to_other(self):
        result = classify_product_text(
            name="Accesorios luna set x3",
            description="",
            dropi_category_name="Bisutería",
        )

        self.assertEqual(result.category_key, "otros")
        self.assertLess(result.confidence, 60)
        self.assertIn("low confidence", result.reason)

    def test_guadana_is_tool_not_fashion_accessory(self):
        result = classify_product_text(
            name="Kit guadañadora 2 baterías + accesorios",
            description="Herramienta de jardín con cuchillas",
            dropi_category_name="Accesorios",
        )

        self.assertEqual(result.category_key, "herramientas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_minoxidil_is_beauty_not_fashion(self):
        result = classify_product_text(
            name="Minoxidil 7% solución capilar 60ml",
            description="Tratamiento para cabello",
            dropi_category_name="Accesorios",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_anti_estrias_is_beauty_not_home(self):
        result = classify_product_text(
            name="Aceite glúteos + crema anti estrías",
            description="Tratamiento corporal reafirmante",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_mojibake_antiestrias_still_beauty(self):
        result = classify_product_text(
            name="Aceite Gluteos + CREMA ANTIESTR�AS",
            description="",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_compact_tool_words_are_detected(self):
        result = classify_product_text(
            name="12llaves + 5destornillador + inflallanta",
            description="Juego de herramientas",
            dropi_category_name="Herramientas",
        )

        self.assertEqual(result.category_key, "herramientas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_board_game_is_toy_not_home_table(self):
        result = classify_product_text(
            name="12 en 1 Juego de Mesa",
            description="Cartas y juegos familiares",
            dropi_category_name="Juguetes",
        )

        self.assertEqual(result.category_key, "juguetes")
        self.assertGreaterEqual(result.confidence, 60)

    def test_antenna_tdt_is_technology(self):
        result = classify_product_text(
            name="Antena TDT de 30 decibeles",
            description="Señal digital para televisión",
            dropi_category_name="Tecnología",
        )

        self.assertEqual(result.category_key, "tecnologia")
        self.assertGreaterEqual(result.confidence, 60)

    def test_perfume_names_become_beauty(self):
        result = classify_product_text(
            name="Antonio Banderas Blue Seduction Men Eau de Parfum",
            description="Fragancia masculina",
            dropi_category_name="",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_anti_snore_product_is_health(self):
        result = classify_product_text(
            name="Antironquidos protector bucal para dormir",
            description="Dispositivo para mejorar respiración nocturna",
            dropi_category_name="",
        )

        self.assertEqual(result.category_key, "salud_bienestar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_chess_set_is_toy(self):
        result = classify_product_text(
            name="Ajedrez madera número 4",
            description="Juego de mesa familiar",
            dropi_category_name="",
        )

        self.assertEqual(result.category_key, "juguetes")
        self.assertGreaterEqual(result.confidence, 60)

    def test_self_threading_needles_are_tools(self):
        result = classify_product_text(
            name="Agujas de coser autoenhebrables",
            description="Kit para costura y reparación",
            dropi_category_name="",
        )

        self.assertEqual(result.category_key, "herramientas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_pet_tray_is_mascotas(self):
        result = classify_product_text(
            name="Bandeja Doggy",
            description="Accesorio para perro",
            dropi_category_name="",
        )

        self.assertEqual(result.category_key, "mascotas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_baby_products_are_not_toys_by_default(self):
        result = classify_product_text(
            name="Coche bebé plegable con portabebé",
            description="Accesorio infantil para paseo",
            dropi_category_name="Bebés",
        )

        self.assertEqual(result.category_key, "bebes")
        self.assertGreaterEqual(result.confidence, 60)

    def test_infant_toy_stays_toy_when_toy_terms_are_specific(self):
        result = classify_product_text(
            name="Patineta infantil con luces",
            description="Juguete para niños",
            dropi_category_name="Juguetes",
        )

        self.assertEqual(result.category_key, "juguetes")
        self.assertGreaterEqual(result.confidence, 60)

    def test_security_camera_uses_security_category(self):
        result = classify_product_text(
            name="Cámara seguridad wifi con sensor movimiento",
            description="Alarma para monitoreo del hogar",
            dropi_category_name="Electrónica",
        )

        self.assertEqual(result.category_key, "seguridad")
        self.assertGreaterEqual(result.confidence, 60)

    def test_motorcycle_alarm_stays_vehicle(self):
        result = classify_product_text(
            name="Alarma moto antirrobo",
            description="Accesorio para motocicleta",
            dropi_category_name="Seguridad",
        )

        self.assertEqual(result.category_key, "vehiculos")
        self.assertGreaterEqual(result.confidence, 60)

    def test_menstrual_cup_is_health_not_tool(self):
        result = classify_product_text(
            name="Copa menstrual reutilizable",
            description="Producto de higiene femenina",
            dropi_category_name="Bienestar",
        )

        self.assertEqual(result.category_key, "salud_bienestar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_plain_polo_is_fashion_not_low_confidence_tool(self):
        result = classify_product_text(
            name="001B1 Polo básica rojo",
            description="",
            dropi_category_name="Moda",
        )

        self.assertEqual(result.category_key, "moda_accesorios")
        self.assertGreaterEqual(result.confidence, 60)

    def test_dental_cream_is_beauty_personal_care(self):
        result = classify_product_text(
            name="Crema dientes blanqueadora bambú",
            description="",
            dropi_category_name="Belleza",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_vacuum_seal_bags_are_kitchen(self):
        result = classify_product_text(
            name="100 bolsas de sellado al vacío empacador",
            description="",
            dropi_category_name="Cocina",
        )

        self.assertEqual(result.category_key, "cocina")
        self.assertGreaterEqual(result.confidence, 60)

    def test_pet_brush_is_not_beauty_brush(self):
        result = classify_product_text(
            name="Super oferta cepillo para mascota",
            description="Cepillo para perro y gato",
            dropi_category_name="Mascotas",
        )

        self.assertEqual(result.category_key, "mascotas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_silicone_socks_are_fashion_not_tools(self):
        result = classify_product_text(
            name="Medias de silicona hidratante",
            description="Prenda para pies",
            dropi_category_name="Moda",
        )

        self.assertEqual(result.category_key, "moda_accesorios")
        self.assertGreaterEqual(result.confidence, 60)

    def test_thermal_bag_for_colic_is_health(self):
        result = classify_product_text(
            name="Bolsa térmica para cólicos",
            description="Alivio de dolor abdominal",
            dropi_category_name="Bienestar",
        )

        self.assertEqual(result.category_key, "salud_bienestar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_compact_camelcase_tool_terms_are_split(self):
        result = classify_product_text(
            name="2 Carbone sTaladro percutor Rmax-7Nx",
            description="Repuesto para herramienta",
            dropi_category_name="Herramientas",
        )

        self.assertEqual(result.category_key, "herramientas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_stationery_products_use_papeleria(self):
        result = classify_product_text(
            name="Cartuchera pines para marcadores",
            description="Útil escolar",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "papeleria")
        self.assertGreaterEqual(result.confidence, 60)

    def test_books_and_coloring_rolls_are_stationery_not_babies(self):
        result = classify_product_text(
            name="4 libros de práctica caligrafía niños",
            description="Rollo de colorear con marcadores",
            dropi_category_name="Libros",
        )

        self.assertEqual(result.category_key, "papeleria")
        self.assertGreaterEqual(result.confidence, 60)

    def test_weekly_pill_organizer_is_health_not_home(self):
        result = classify_product_text(
            name="Organizador semanal de pastillas",
            description="Pastillero día y noche",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "salud_bienestar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_compact_watch_brand_is_fashion(self):
        result = classify_product_text(
            name="RELOJJOEFOX ANA-DIG METAL TRES HRS HM",
            description="Reloj de hombre",
            dropi_category_name="Moda",
        )

        self.assertEqual(result.category_key, "moda_accesorios")
        self.assertGreaterEqual(result.confidence, 60)

    def test_smartwatch_is_technology_not_fashion_watch(self):
        result = classify_product_text(
            name="Reloj SmartWatch T500 doble pulso",
            description="Dispositivo bluetooth recargable",
            dropi_category_name="Tecnología",
        )

        self.assertEqual(result.category_key, "tecnologia")
        self.assertGreaterEqual(result.confidence, 60)

    def test_perfume_dropi_category_is_beauty_even_with_brand_only_name(self):
        result = classify_product_text(
            name="360 Coral",
            description="",
            dropi_category_name="Perfumes",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_tool_set_phrase_stays_tools(self):
        result = classify_product_text(
            name="Juego de herramientas 51 piezas",
            description="Incluye llave inglesa y adaptador",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "herramientas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_pinateria_party_supplies_use_fiesta_category(self):
        result = classify_product_text(
            name="Plato cartón amarillo borde dorado x10",
            description="Vajilla para cumpleaños",
            dropi_category_name="Piñateria",
        )

        self.assertEqual(result.category_key, "fiesta_pinateria")
        self.assertGreaterEqual(result.confidence, 60)

    def test_halloween_costumes_use_fiesta_category(self):
        result = classify_product_text(
            name="Alas de hada disfraz infantil Halloween",
            description="Accesorio para fiesta",
            dropi_category_name="Halloween",
        )

        self.assertEqual(result.category_key, "fiesta_pinateria")
        self.assertGreaterEqual(result.confidence, 60)

    def test_shoe_brands_and_boots_are_fashion(self):
        result = classify_product_text(
            name="Bota Caterpillar 013 Alaska rosa puntera",
            description="Calzado para dama",
            dropi_category_name="Moda",
        )

        self.assertEqual(result.category_key, "moda_accesorios")
        self.assertGreaterEqual(result.confidence, 60)

    def test_hydrogel_pistol_is_toy_not_security(self):
        result = classify_product_text(
            name="Bolsa de bolas para pistola de hidrogel",
            description="Munición para juguete",
            dropi_category_name="Jugueteria",
        )

        self.assertEqual(result.category_key, "juguetes")
        self.assertGreaterEqual(result.confidence, 60)

    def test_lubricant_intimate_products_use_intimate_wellness(self):
        result = classify_product_text(
            name="Gel anal lubricante íntimo Expand",
            description="Producto adulto",
            dropi_category_name="Sex Shop",
        )

        self.assertEqual(result.category_key, "bienestar_intimo")
        self.assertGreaterEqual(result.confidence, 60)

    def test_tool_replacement_charger_stays_tools_not_technology(self):
        result = classify_product_text(
            name="2 baterías + cargador guadaña repuesto",
            description="Accesorio para herramienta",
            dropi_category_name="Herramientas",
        )

        self.assertEqual(result.category_key, "herramientas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_printer_rolls_from_toy_category_go_to_stationery(self):
        result = classify_product_text(
            name="1 rollo adhesivos mini impresora",
            description="Papel para impresión",
            dropi_category_name="Jugueteria",
        )

        self.assertEqual(result.category_key, "papeleria")
        self.assertGreaterEqual(result.confidence, 60)

    def test_baby_walker_from_toy_category_goes_to_babies(self):
        result = classify_product_text(
            name="Andador 2 en 1 para bebés",
            description="Caminador primeros pasos",
            dropi_category_name="Jugueteria",
        )

        self.assertEqual(result.category_key, "bebes")
        self.assertGreaterEqual(result.confidence, 60)

    def test_abrelatas_uses_kitchen_not_home_fallback(self):
        result = classify_product_text(
            name="Abrelatas eléctrico automático",
            description="Utensilio de cocina",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "cocina")
        self.assertGreaterEqual(result.confidence, 60)

    def test_angel_wings_with_led_stay_party_not_technology(self):
        result = classify_product_text(
            name="Alas angel negro luz LED",
            description="",
            dropi_category_name="Tecnologia",
        )

        self.assertEqual(result.category_key, "fiesta_pinateria")
        self.assertGreaterEqual(result.confidence, 60)

    def test_cooling_gel_patch_is_health_not_home(self):
        result = classify_product_text(
            name="Parche de gel de enfriamient x5",
            description="",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "salud_bienestar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_air_conditioner_is_home_not_technology(self):
        result = classify_product_text(
            name="Aire acondicionado",
            description="",
            dropi_category_name="Tecnologia",
        )

        self.assertEqual(result.category_key, "hogar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_tool_adapter_with_screws_stays_tools_not_technology(self):
        result = classify_product_text(
            name="Adaptador de pistola de tornillos x50",
            description="",
            dropi_category_name="Herramientas",
        )

        self.assertEqual(result.category_key, "herramientas")
        self.assertGreaterEqual(result.confidence, 60)

    def test_detox_foot_pads_are_health_not_home(self):
        result = classify_product_text(
            name="10 almohadillas desintoxicantes pies",
            description="",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "salud_bienestar")
        self.assertGreaterEqual(result.confidence, 60)

    def test_deodorant_rollon_is_beauty_not_home(self):
        result = classify_product_text(
            name="Desodorante rollon para hombre",
            description="",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "belleza")
        self.assertGreaterEqual(result.confidence, 60)

    def test_educational_abacus_is_stationery_not_home(self):
        result = classify_product_text(
            name="Abaco educativo para aprender matemática",
            description="",
            dropi_category_name="Hogar",
        )

        self.assertEqual(result.category_key, "papeleria")
        self.assertGreaterEqual(result.confidence, 60)

    def test_recategorize_dry_run_does_not_create_store_categories(self):
        raw = Category.objects.create(dropi_id="raw-paper", name="Hogar")
        Product.objects.create(
            dropi_id=77003,
            name="Cartuchera pines para marcadores",
            description="",
            dropi_category_name="Hogar",
            category=raw,
            price=10000,
            stock=1,
            is_active=True,
        )
        out = StringIO()

        call_command("recategorize_products", dry_run=True, quiet=True, limit=1, stdout=out)

        self.assertIn("DRY RUN", out.getvalue())
        self.assertFalse(Category.objects.filter(dropi_id="store:papeleria").exists())

    def test_ambiguous_color_name_stays_other(self):
        result = classify_product_text(
            name="360 Coral",
            description="",
            dropi_category_name="",
        )

        self.assertEqual(result.category_key, "otros")

    def test_upsert_product_assigns_store_category_and_keeps_dropi_raw_data(self):
        product, _created = upsert_product({
            "id": 77001,
            "name": "Kit maquillaje profesional",
            "description": "Sombras, brochas y cosméticos para belleza",
            "sale_price": "10000",
            "suggested_price": "25000",
            "categories": [{"name": "Belleza Y Cuidado Personal", "pivot": {"category_id": 1419}}],
        })

        self.assertEqual(product.category.name, "Belleza")
        self.assertEqual(product.dropi_category_id, "1419")
        self.assertEqual(product.dropi_category_name, "Belleza Y Cuidado Personal")
        self.assertFalse(product.category_locked)

    def test_upsert_product_does_not_override_locked_store_category(self):
        manual = ensure_store_category("tecnologia")
        product = Product.objects.create(
            dropi_id=77002,
            name="Producto manual",
            description="",
            category=manual,
            category_locked=True,
            price=10000,
            stock=1,
            is_active=True,
        )

        updated, _created = upsert_product({
            "id": product.dropi_id,
            "name": "Kit maquillaje profesional",
            "description": "Sombras y cosméticos para belleza",
            "sale_price": "10000",
            "categories": [{"name": "Belleza", "pivot": {"category_id": 7}}],
        })

        self.assertEqual(updated.category, manual)
        self.assertTrue(updated.category_locked)


class ProductReviewServiceTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="rev-cat", name="Reseñas")
        self.product = Product.objects.create(
            dropi_id=888001,
            name="Producto con reseñas",
            category=self.cat,
            price=50000,
            stock=5,
            is_active=True,
            slug="producto-reviews",
        )
        self.staff = User.objects.create_user(
            username="staff_reviewer",
            password="test-pass-123",
            is_staff=True,
        )
        self.buyer = User.objects.create_user(
            username="buyer_reviewer",
            email="buyer@test.com",
            password="test-pass-123",
        )

    def test_no_rating_until_published_reviews(self):
        self.assertFalse(self.product.display_rating_is_real)
        self.assertIsNone(self.product.display_rating)

    def test_recalculate_updates_aggregates(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.staff,
            score=5,
            is_published=True,
        )
        recalculate_product_rating(self.product.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(float(self.product.rating_average), 5.0)
        self.assertTrue(self.product.display_rating_is_real)
        self.assertEqual(self.product.display_rating, 5.0)

    def _order_with_product(self, user):
        return Order.objects.create(
            user=user,
            name="Test",
            surname="Buyer",
            email=user.email or "buyer@test.com",
            phone="5500000000",
            address="Calle 1",
            city="Guadalajara",
            state="JAL",
            total=50000,
            items=[
                {
                    "product_id": self.product.pk,
                    "dropi_id": self.product.dropi_id,
                    "name": self.product.name,
                    "quantity": 1,
                    "price": "50000",
                }
            ],
            status=Order.STATUS_PENDING,
        )

    def test_submit_review_via_service_after_purchase(self):
        self._order_with_product(self.buyer)
        review = submit_review(
            product=self.product,
            user=self.buyer,
            score=4,
            comment="Muy bueno",
        )
        self.product.refresh_from_db()
        self.assertEqual(review.score, 4)
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(float(self.product.rating_average), 4.0)

    def test_non_staff_without_purchase_cannot_review(self):
        with self.assertRaises(PermissionDenied):
            submit_review(product=self.product, user=self.buyer, score=3)

    def test_staff_without_purchase_cannot_review_via_service(self):
        with self.assertRaises(PermissionDenied):
            submit_review(product=self.product, user=self.staff, score=5)

    def test_product_detail_shows_published_reviews(self):
        self._order_with_product(self.buyer)
        review = submit_review(product=self.product, user=self.buyer, score=5, comment="")
        review.is_published = True
        review.save(update_fields=["is_published"])
        url = self.product.get_absolute_url()
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="reviews"')


class ShippingExperimentTests(TestCase):
    """needs_combo bucket only — envío real + razón, y su instrumentación."""

    def setUp(self):
        self.cat = Category.objects.create(dropi_id="shipexp1", name="Categoria Combo")
        # margin=5 -> shipping_gap = 120-5 = 115 > SHIPPING_CEILING (85) -> needs_combo
        self.needs_combo_product = Product.objects.create(
            dropi_id=777001,
            name="Producto Margen Bajo",
            category=self.cat,
            cost=100,
            price=105,
            stock=10,
            is_active=True,
            slug="producto-margen-bajo",
            supplier_id=55,
        )
        # margin=800, 400% markup -> is_profitable, not needs_combo -> valid combo partner
        self.combo_partner = Product.objects.create(
            dropi_id=777002,
            name="Producto Rentable Combo",
            category=self.cat,
            cost=200,
            price=1000,
            stock=10,
            is_active=True,
            slug="producto-rentable-combo",
            supplier_id=55,
        )

    def _order(self, items, total):
        return Order.objects.create(
            name="Test", surname="Buyer", email="buyer@test.com", phone="5500000000",
            address="Calle 1", city="Guadalajara", state="JAL", total=total,
            items=items, status=Order.STATUS_CONFIRMED,
        )

    def test_needs_combo_true_for_thin_margin_product(self):
        self.assertTrue(self.needs_combo_product.needs_combo)
        self.assertFalse(self.combo_partner.needs_combo)

    def test_reason_is_zone_based_outside_zone_a(self):
        from catalog.services.shipping_experiment import build_shipping_experiment_context
        ctx = build_shipping_experiment_context(self.needs_combo_product, "Tepic")
        self.assertEqual(ctx["zone"], "B")
        self.assertIn("cobertura extendida", ctx["reason_short"])

    def test_reason_is_margin_based_in_zone_a(self):
        # In Zone A (the baseline needs_combo is computed against) the real
        # cause can't honestly be "coverage" — it's the product's own margin.
        from catalog.services.shipping_experiment import build_shipping_experiment_context
        ctx = build_shipping_experiment_context(self.needs_combo_product, "Guadalajara")
        self.assertEqual(ctx["zone"], "A")
        self.assertIn("más alto que el promedio", ctx["reason_short"])
        self.assertNotIn("cobertura extendida", ctx["reason_short"])

    def test_combo_candidates_exclude_other_needs_combo_products(self):
        from catalog.services.combo_suggestions import suggest_combo_candidates
        candidates = suggest_combo_candidates(self.needs_combo_product)
        self.assertIn(self.combo_partner, candidates)

    def test_log_shown_creates_event(self):
        from catalog.services.shipping_experiment import build_shipping_experiment_context, log_shown
        ctx = build_shipping_experiment_context(self.needs_combo_product, "Guadalajara")
        log_shown(self.needs_combo_product, ctx, session_key="abc123")
        event = ShippingExperimentEvent.objects.get()
        self.assertEqual(event.event_type, ShippingExperimentEvent.EVENT_SHOWN)
        self.assertEqual(event.product, self.needs_combo_product)
        self.assertEqual(event.session_key, "abc123")

    def test_purchase_outcome_surcharge_when_bought_alone(self):
        from catalog.services.shipping_experiment import log_purchase_outcome
        order = self._order(
            items=[{
                "product_id": self.needs_combo_product.pk,
                "dropi_id": self.needs_combo_product.dropi_id,
                "name": self.needs_combo_product.name,
                "quantity": 1, "price": "105",
            }],
            total=105,
        )
        log_purchase_outcome(order)
        event = ShippingExperimentEvent.objects.get()
        self.assertEqual(event.event_type, ShippingExperimentEvent.EVENT_PURCHASED_SURCHARGE)
        self.assertEqual(event.order, order)
        self.assertEqual(event.product, self.needs_combo_product)

    def test_purchase_outcome_combo_when_bought_with_candidate(self):
        from catalog.services.shipping_experiment import log_purchase_outcome
        order = self._order(
            items=[
                {
                    "product_id": self.needs_combo_product.pk,
                    "dropi_id": self.needs_combo_product.dropi_id,
                    "name": self.needs_combo_product.name,
                    "quantity": 1, "price": "10500",
                },
                {
                    "product_id": self.combo_partner.pk,
                    "dropi_id": self.combo_partner.dropi_id,
                    "name": self.combo_partner.name,
                    "quantity": 1, "price": "100000",
                },
            ],
            total=110500,
        )
        log_purchase_outcome(order)
        # Only the needs_combo product gets an event — its profitable partner isn't instrumented.
        event = ShippingExperimentEvent.objects.get()
        self.assertEqual(event.event_type, ShippingExperimentEvent.EVENT_CHOSE_COMBO)
        self.assertEqual(event.product, self.needs_combo_product)

    def test_product_detail_renders_experiment_block_and_logs_shown(self):
        session = self.client.session
        session["visitor_city"] = {"city": "Tepic", "state": "Nayarit"}
        session.save()
        res = self.client.get(self.needs_combo_product.get_absolute_url())
        self.assertContains(res, "shipping-experiment")
        self.assertContains(res, self.combo_partner.name.title())
        self.assertEqual(
            ShippingExperimentEvent.objects.filter(
                product=self.needs_combo_product, event_type=ShippingExperimentEvent.EVENT_SHOWN
            ).count(),
            1,
        )

    def test_product_detail_hides_experiment_until_city_is_known(self):
        res = self.client.get(self.needs_combo_product.get_absolute_url())
        self.assertNotContains(res, "shipping-experiment__amount")
        self.assertFalse(ShippingExperimentEvent.objects.exists())

    def test_product_detail_does_not_log_for_normal_products(self):
        self.client.get(self.combo_partner.get_absolute_url())
        self.assertFalse(ShippingExperimentEvent.objects.exists())


class ContentGenerationTests(TestCase):
    """Generación de meta_title/meta_description/description_unique por
    plantillas — sin IA. Ver catalog/services/content_generation.py."""

    def setUp(self):
        self.cat = Category.objects.create(dropi_id="content-gen-1", name="Tecnología")
        self.product = Product.objects.create(
            dropi_id=888101,
            name="Reloj Smart Watch WS-6 ⚡",
            category=self.cat,
            price=100000,
            cost=40000,
            stock=10,
            is_active=True,
            slug="reloj-smart-watch-ws-6",
            description=(
                "<p>Con la App podrás dar seguimiento a tus rutinas de ejercicio "
                "desde tu teléfono con toda la información enviada desde el reloj.</p>"
                "<p>Mal uso del producto: Incluyendo golpes, caídas, exposición a "
                "líquidos, altas temperaturas, sobrecarga eléctrica o cualquier otra "
                "acción que no se ajuste al manual de usuario.</p>"
            ),
        )

    def test_excludes_warranty_boilerplate_from_anchor(self):
        """Regresión: un producto real generó 'Entre sus características: Mal
        uso del producto...' porque la cláusula de garantía era el candidato
        más largo. La ancla real (features) debe ganar sobre el texto legal."""
        from catalog.services.content_generation import extract_anchor_sentence

        anchor = extract_anchor_sentence(self.product.description)
        self.assertIn("seguimiento", anchor.lower())
        self.assertNotIn("mal uso", anchor.lower())
        self.assertNotIn("manual de usuario", anchor.lower())

    def test_cuts_off_numbered_warranty_policy_section(self):
        """Regresión real: una descripción completa (reloj inteligente) tenía
        ~15 líneas de características reales seguidas de una política de
        garantías con 10+ cláusulas ("1. Alcance:", "Producto no funciona:",
        "7. Resolución:"...). Ninguna de esas cláusulas está en el blocklist
        de palabras — el fix real es cortar todo lo que viene después del
        encabezado numerado, no perseguir cada frase de garantía una por
        una."""
        from catalog.services.content_generation import extract_anchor_sentence

        description = (
            "<p>Desde el Smartwatch puedes hacer llamadas y contestar llamadas "
            "de tu celular por medio de conexión bluetooth con micrófono y "
            "altavoz incorporado.</p>"
            "<p>Pantalla grande de 1,86 pulgadas, pantalla táctil completa.</p>"
            "<p>1. Alcance:</p>"
            "<p>Esta política de garantías se aplica a todos los productos.</p>"
            "<p>Producto no funciona: Si el producto no enciende o presenta fallas recurrentes.</p>"
            "<p>7. Resolución:</p>"
            "<p>Reparar el producto: Si la falla puede ser reparada.</p>"
        )
        anchor = extract_anchor_sentence(description)
        self.assertIn("llamadas", anchor.lower())
        self.assertNotIn("no funciona", anchor.lower())
        self.assertNotIn("reparar", anchor.lower())
        self.assertNotIn("alcance", anchor.lower())

    def test_has_usable_name(self):
        from catalog.services.content_generation import has_usable_name

        self.assertTrue(has_usable_name("Reloj Smart Watch WS-6"))
        self.assertFalse(has_usable_name(".."))
        self.assertFalse(has_usable_name("001"))
        self.assertFalse(has_usable_name(""))

    def test_generate_unique_content_is_deterministic(self):
        from catalog.services.content_generation import generate_unique_content

        first = generate_unique_content(self.product)
        second = generate_unique_content(self.product)
        self.assertEqual(first, second)

    def test_meta_description_uses_anchor_not_generic_benefit(self):
        from catalog.services.content_generation import generate_unique_content

        content = generate_unique_content(self.product)
        self.assertIn("seguimiento", content["meta_description"].lower())

    def test_seo_meta_description_prefers_curated_field(self):
        from catalog.seo import generate_meta_description

        self.product.meta_description = "Descripción curada a mano."
        self.assertEqual(generate_meta_description(self.product), "Descripción curada a mano.")

    def test_seo_meta_description_falls_back_when_empty(self):
        from catalog.seo import generate_meta_description

        self.assertIn("seguimiento", generate_meta_description(self.product).lower())

    def test_detail_page_uses_meta_title_when_set(self):
        self.product.meta_title = "Título SEO Curado"
        self.product.save(update_fields=["meta_title"])
        res = self.client.get(self.product.get_absolute_url())
        self.assertContains(res, "<title>Título SEO Curado</title>")

    def test_detail_page_falls_back_to_name_when_no_meta_title(self):
        from catalog.seo import generate_seo_title

        res = self.client.get(self.product.get_absolute_url())
        title = generate_seo_title(self.product)
        self.assertContains(res, f"<title>{title}</title>")
        self.assertTrue(title.endswith("Pegasus Store"))
        self.assertNotIn("⚡", title)

    def test_detail_page_shows_description_unique_when_set(self):
        self.product.description_unique = "Texto único generado por plantillas."
        self.product.save(update_fields=["description_unique"])
        res = self.client.get(self.product.get_absolute_url())
        self.assertContains(res, "Texto único generado por plantillas.")

    def test_detail_page_falls_back_to_raw_description_when_no_unique(self):
        res = self.client.get(self.product.get_absolute_url())
        self.assertContains(res, "seguimiento a tus rutinas")
