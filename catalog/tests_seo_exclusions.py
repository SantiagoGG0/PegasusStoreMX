import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from .models import Category, Product


def _product(dropi_id, slug, **kwargs):
    data = dict(
        dropi_id=dropi_id, name=slug, slug=slug, price=Decimal("30000"),
        cost=Decimal("10000"), stock=5, is_active=True,
    )
    data.update(kwargs)
    return Product.objects.create(**data)


class LoadSeoExclusionsCommandTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        self.envio = _product(1, "envio-prioritario", category=self.cat)
        self.parche = _product(2, "parche-adelgazante", category=self.cat)
        self.keep = _product(3, "encendedor", category=self.cat)
        self.dup = _product(4, "encendedor-2", category=self.cat)
        self.inactive_target = _product(5, "molde", category=self.cat, is_active=False)
        self.dup_of_inactive = _product(6, "molde-1", category=self.cat)
        self.taser = _product(7, "taser", category=self.cat)

    def _csv(self, body):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        tmp.write("slug;exclusion;canonical_slug\n" + body)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def _run(self, path, *extra):
        out = StringIO()
        call_command("load_seo_exclusions", "--file", path, *extra, stdout=out)
        return out.getvalue()

    def test_dry_run_only_counts(self):
        out = self._run(self._csv("envio-prioritario;b;\nencendedor-2;;encendedor\n"), "--dry-run")
        self.assertIn("[dry-run] Productos que cambian: 2", out)
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.seo_exclusion, "")

    def test_applies_exclusions_and_canonicals_by_slug(self):
        before = Product.objects.get(pk=self.envio.pk).last_synced
        self._run(self._csv(
            "envio-prioritario;b;\nparche-adelgazante;c1;\ntaser;e;\n"
            "encendedor-2;;encendedor\nmolde-1;;molde\nno-existe;a1;\n"
        ))
        values = dict(Product.objects.values_list("slug", "seo_exclusion"))
        self.assertEqual(values["envio-prioritario"], "b")
        self.assertEqual(values["parche-adelgazante"], "c1")
        self.assertEqual(values["taser"], "e")
        self.dup.refresh_from_db()
        self.assertEqual(self.dup.canonical_product_id, self.keep.pk)
        self.dup_of_inactive.refresh_from_db()
        self.assertIsNone(self.dup_of_inactive.canonical_product_id)  # destino inactivo
        # bulk_update no toca last_synced (lastmod del sitemap).
        self.assertEqual(Product.objects.get(pk=self.envio.pk).last_synced, before)

    def test_sync_clears_products_no_longer_listed(self):
        self._run(self._csv("envio-prioritario;b;\nencendedor-2;;encendedor\n"))
        self._run(self._csv("parche-adelgazante;c2;\n"))
        self.envio.refresh_from_db()
        self.dup.refresh_from_db()
        self.assertEqual(self.envio.seo_exclusion, "")
        self.assertIsNone(self.dup.canonical_product_id)

    def test_unknown_exclusion_code_fails(self):
        with self.assertRaises(CommandError):
            self._run(self._csv("envio-prioritario;zz;\n"))


class ProductQuerySetTests(TestCase):
    def test_listable_and_indexable(self):
        keep = _product(10, "a")
        _product(11, "b-noindex", seo_exclusion="c1")
        _product(12, "e-adulto", seo_exclusion="e")
        _product(13, "a-2", canonical_product=keep)
        self.assertEqual(sorted(Product.objects.listable().values_list("slug", flat=True)), ["a", "a-2"])
        self.assertEqual(sorted(Product.objects.indexable().values_list("slug", flat=True)), ["a"])


class DuplicateCanonicalTests(TestCase):
    """Casi duplicados: rel=canonical hacia la ficha que se mantiene (sin noindex)."""

    def setUp(self):
        self.keep = _product(20, "encendedor")
        self.dup = _product(21, "encendedor-2", canonical_product=self.keep)

    def test_duplicate_points_canonical_to_kept_product(self):
        html = self.client.get("/producto/encendedor-2/").content.decode()
        self.assertRegex(html, r'<link rel="canonical" href="[^"]*/producto/encendedor/">')
        self.assertNotIn("noindex", html)

    def test_kept_product_is_self_canonical(self):
        html = self.client.get("/producto/encendedor/").content.decode()
        self.assertRegex(html, r'<link rel="canonical" href="[^"]*/producto/encendedor/">')

    def test_falls_back_to_self_when_target_inactive(self):
        Product.objects.filter(pk=self.keep.pk).update(is_active=False)
        html = self.client.get("/producto/encendedor-2/").content.decode()
        self.assertRegex(html, r'<link rel="canonical" href="[^"]*/producto/encendedor-2/">')


class ExclusionBehaviourTests(TestCase):
    """b/c1/c2/c3/a1/e: noindex, fuera del sitemap y de listas. d: fuera del
    sitemap, sigue en listas, sin noindex."""

    def setUp(self):
        self.cat = Category.objects.create(dropi_id="store:belleza", name="Belleza")
        self.normal = _product(30, "crema-hidratante", category=self.cat, name="Crema hidratante", is_featured=True)
        self.claim = _product(31, "parche-adelgazante", category=self.cat, name="Parche adelgazante", seo_exclusion="c1", is_featured=True)
        self.adult = _product(32, "taser-x", category=self.cat, name="Taser defensa", seo_exclusion="e", is_featured=True)
        self.dup = _product(33, "crema-hidratante-2", category=self.cat, name="Crema hidratante 2", canonical_product=self.normal)

    def test_noindex_only_for_policy_criteria(self):
        for slug in ("parche-adelgazante", "taser-x"):
            self.assertIn('content="noindex,follow"', self.client.get(f"/producto/{slug}/").content.decode(), slug)
        for slug in ("crema-hidratante-2", "crema-hidratante"):
            self.assertNotIn("noindex", self.client.get(f"/producto/{slug}/").content.decode(), slug)

    def test_sitemap_excludes_noindex_and_duplicates(self):
        from django.core.cache import cache

        cache.clear()
        xml = self.client.get("/sitemap-productos.xml").content.decode()
        self.assertIn("/producto/crema-hidratante/<", xml)
        self.assertNotIn("/producto/taser-x/<", xml)
        self.assertNotIn("/producto/parche-adelgazante/<", xml)
        self.assertNotIn("/producto/crema-hidratante-2/<", xml)

    def test_category_listing_and_search_exclude_policy_and_e(self):
        for url in ("/categoria/belleza/", "/?view=all", "/?q=a"):
            slugs = [p.slug for p in self.client.get(url).context["home_sections"][-1].context["page_obj"]]
            self.assertIn("crema-hidratante", slugs, url)
            self.assertIn("crema-hidratante-2", slugs, url)
            self.assertNotIn("parche-adelgazante", slugs, url)
            self.assertNotIn("taser-x", slugs, url)

    def test_search_suggestions_exclude(self):
        for q, slug in (("parche", "parche-adelgazante"), ("taser", "taser-x")):
            data = self.client.get("/buscar/sugerencias/", {"q": q}).json()
            self.assertNotIn(f"/producto/{slug}/", [r["url"] for r in data["results"]])

    def test_home_featured_excludes(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("/producto/parche-adelgazante/", html)
        self.assertNotIn("/producto/taser-x/", html)


class BuildSeoExclusionsScriptTests(TestCase):
    """Reglas del generador catalog/data/build_seo_exclusions.py: protegidos,
    criterio e y elección de la ficha canónica en duplicados."""

    def _build(self, products):
        import importlib.util
        import sqlite3

        path = Path(__file__).resolve().parent / "data" / "build_seo_exclusions.py"
        spec = importlib.util.spec_from_file_location("build_seo_exclusions", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Lista propia del test: la real está vacía hasta que México tenga tráfico orgánico.
        protected = Path(tempfile.mkdtemp()) / "protected.txt"
        protected.write_text("taladro-dewalt-pantalla\nretardante-brocha-pincelada-china-10ml\nlampara-lava-1\n",
                             encoding="utf-8")
        module.PROTECTED_FILE = protected

        tmp = Path(tempfile.mkdtemp())
        db = sqlite3.connect(tmp / "db.sqlite3")
        db.execute("create table catalog_category (id integer primary key, dropi_id text)")
        db.execute("create table catalog_product (id integer primary key, slug text, name text, description text,"
                   " category_id integer, price real, stock integer)")
        db.execute("insert into catalog_category values (1, 'store:hogar'), (2, 'store:bienestar_intimo')")
        for i, (slug, name, cat, stock) in enumerate(products, start=1):
            db.execute("insert into catalog_product values (?, ?, ?, '', ?, 30000, ?)", (i, slug, name, cat, stock))
        db.commit()
        db.close()
        sitemap = tmp / "sitemap.xml"
        sitemap.write_text("".join(f"<loc>https://x/producto/{p[0]}/</loc>" for p in products), encoding="utf-8")
        rows, _info, _missing = module.build(tmp / "db.sqlite3", sitemap)
        return {r[0]: (r[1], r[2]) for r in rows}

    def test_rules(self):
        rows = self._build([
            ("taladro-dewalt-pantalla", "Taladro Dewalt pantalla", 1, 5),        # a1 protegido
            ("taladro-dewalt-x", "Taladro Dewalt X", 1, 5),                      # a1
            ("retardante-brocha-pincelada-china-10ml", "Retardante brocha", 1, 5),  # protegido, pero c1
            ("taser-928", "Taser 928", 1, 5),                                      # e
            ("lubricante-cereza", "Lubricante cereza", 2, 5),                      # e por categoría
            ("vibrador-de-baldosas", "Vibrador de baldosas", 1, 5),               # herramienta: nada
            ("cable-para-iphone", "Cable para iPhone", 1, 5),                     # a2: nada
            ("encendedor", "Encendedor", 1, 5),
            ("encendedor-1", "Encendedor", 1, 5),                                  # d → encendedor
            ("lampara-lava", "Lampara lava", 1, 5),
            ("lampara-lava-1", "Lampara lava", 1, 5),                              # d, pero protegido
        ])
        self.assertNotIn("taladro-dewalt-pantalla", rows)
        self.assertEqual(rows["taladro-dewalt-x"], ("a1", ""))
        self.assertEqual(rows["retardante-brocha-pincelada-china-10ml"][0], "c1")
        self.assertEqual(rows["taser-928"], ("e", ""))
        self.assertEqual(rows["lubricante-cereza"], ("e", ""))
        self.assertNotIn("vibrador-de-baldosas", rows)
        self.assertNotIn("cable-para-iphone", rows)
        self.assertEqual(rows["encendedor-1"], ("", "encendedor"))
        self.assertNotIn("lampara-lava-1", rows)


class NoindexWinsOverCanonicalTests(TestCase):
    def test_command_drops_canonical_for_noindex_products(self):
        keep = _product(40, "encendedor")
        adult = _product(41, "encendedor-2")
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        tmp.write("slug;exclusion;canonical_slug\nencendedor-2;e;encendedor\n")
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        call_command("load_seo_exclusions", "--file", tmp.name, stdout=StringIO())
        adult.refresh_from_db()
        self.assertEqual(adult.seo_exclusion, "e")
        self.assertIsNone(adult.canonical_product_id)
        self.assertTrue(adult.seo_noindex)
        self.assertEqual(keep.pk, Product.objects.get(slug="encendedor").pk)
