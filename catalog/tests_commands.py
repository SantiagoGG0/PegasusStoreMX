from decimal import Decimal
from importlib import import_module
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from catalog.models import Category, Product

COMMANDS_DIR = Path(__file__).parent / "management" / "commands"


class ManagementCommandsImportTests(SimpleTestCase):
    """Los comandos de catálogo corren contra producción sin tests propios:
    al menos deben cargar (un error de sintaxis solo aparecería en vivo)."""

    def test_every_command_imports(self):
        names = sorted(p.stem for p in COMMANDS_DIR.glob("*.py") if p.stem != "__init__")
        self.assertIn("sync_galleries", names)
        for name in names:
            with self.subTest(command=name):
                module = import_module(f"catalog.management.commands.{name}")
                self.assertTrue(hasattr(module, "Command"))


class RebalanceCatalogTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="store:otros", name="Otros")

    def _product(self, dropi_id, **kwargs):
        defaults = dict(
            name=f"P{dropi_id}", slug=f"p{dropi_id}", category=self.cat, cost=10_000, price=30_000,
            stock=5, images=[{"url": "https://x/1.jpg"}], suggested_price=25_000,
        )
        defaults.update(kwargs)
        return Product.objects.create(dropi_id=dropi_id, **defaults)

    def test_apply(self):
        no_variant_stock = self._product(1, is_active=True, variants=[
            {"id": 11, "warehouse_product_variation": [{"stock": 0}]},
            {"id": 12, "warehouse_product_variation": [{"stock": 0}]},
        ])
        sellable = self._product(2, is_active=True, variants=[{"id": 21, "warehouse_product_variation": [{"stock": 3}]}])
        old_inactive = self._product(3, is_active=False)
        flagged = self._product(4, is_active=False, image_flagged=True)
        not_in_dropi = self._product(5, is_active=False, suggested_price=0)

        call_command("rebalance_catalog", "--apply", stdout=StringIO())

        states = {p.pk: (p.is_active, p.inactive_reason) for p in Product.objects.all()}
        self.assertEqual(states[no_variant_stock.pk], (False, "sin_stock"))
        self.assertEqual(states[sellable.pk], (True, ""))
        self.assertEqual(states[old_inactive.pk], (True, ""))
        self.assertFalse(states[flagged.pk][0])
        self.assertFalse(states[not_in_dropi.pk][0])


class ConsolidateSeoTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="store:otros", name="Otros")

    def _p(self, dropi_id, name, **kw):
        defaults = dict(slug=f"s{dropi_id}", category=self.cat, cost=10_000, price=30_000, stock=5,
                        is_active=True, images=[{"url": "https://x/1.jpg"}])
        defaults.update(kw)
        return Product.objects.create(dropi_id=dropi_id, name=name, **defaults)

    def test_duplicates_point_to_best_and_junk_is_excluded(self):
        weak = self._p(1, "Secador de Zapatos", rank_score=40)
        best = self._p(2, "SECADOR DE ZAPATOS", rank_score=30,
                       images=[{"url": "https://x/1.jpg"}, {"url": "https://x/2.jpg"}])
        other = self._p(3, "Secador de zapatos", rank_score=90)
        unique = self._p(4, "Lámpara de escritorio")
        junk = self._p(5, "ENVIO PRIORITARIO")
        lock = self._p(6, "Candado seguro bicicleta")

        call_command("consolidate_seo", "--apply", stdout=StringIO())
        state = {p.pk: (p.canonical_product_id, p.seo_exclusion) for p in Product.objects.all()}

        self.assertEqual(state[best.pk], (None, ""))            # 2 fotos gana aunque tenga menos relevancia
        self.assertEqual(state[weak.pk], (best.pk, ""))
        self.assertEqual(state[other.pk], (best.pk, ""))
        self.assertEqual(state[unique.pk], (None, ""))
        self.assertEqual(state[junk.pk][1], "b")
        self.assertEqual(state[lock.pk], (None, ""))            # "seguro" de candado no es basura
        self.assertTrue(Product.objects.get(pk=weak.pk).is_active)   # sigue a la venta

    def test_sold_and_organic_products_never_point_elsewhere(self):
        from orders.models import Order

        best = self._p(20, "Zapatero metálico", images=[{"url": "https://x/1.jpg"}, {"url": "https://x/2.jpg"}])
        sold = self._p(21, "ZAPATERO METALICO")
        organic = self._p(22, "Zapatero Metálico", slug="ab-tomic-para-para-abdominales-profesion")
        plain = self._p(23, "zapatero metalico")
        Order.objects.create(name="A", surname="B", email="a@b.co", phone="3000000000", address="x", city="Cali",
                             state="VAC", payment_method=Order.PAYMENT_COD, total=1, items=[{"product_id": sold.pk}])
        Product.objects.filter(pk=sold.pk).update(canonical_product=best)

        import tempfile
        from unittest import mock

        protected = Path(tempfile.mkdtemp()) / "protected.txt"
        protected.write_text("ab-tomic-para-para-abdominales-profesion\n", encoding="utf-8")
        with mock.patch("catalog.services.seo_consolidation.PROTECTED_SLUGS_FILE", protected):
            call_command("consolidate_seo", "--apply", stdout=StringIO())
        canon = dict(Product.objects.values_list("pk", "canonical_product_id"))

        self.assertIsNone(canon[sold.pk])        # vendido: recupera su propia canónica
        self.assertIsNone(canon[organic.pk])     # slug con tráfico orgánico
        self.assertEqual(canon[plain.pk], best.pk)  # la ficha principal no cambia
        self.assertIsNone(canon[best.pk])

    def test_existing_main_is_kept_when_scores_change(self):
        old_main = self._p(30, "Lonchera eléctrica")
        rival = self._p(31, "LONCHERA ELECTRICA", images=[{"url": "https://x/1.jpg"}, {"url": "https://x/2.jpg"}])
        Product.objects.filter(pk=rival.pk).update(canonical_product=old_main)

        call_command("consolidate_seo", "--apply", stdout=StringIO())
        canon = dict(Product.objects.values_list("pk", "canonical_product_id"))

        self.assertIsNone(canon[old_main.pk])          # sigue siendo la principal
        self.assertEqual(canon[rival.pk], old_main.pk)  # aunque la otra ahora tenga más fotos

    def test_duplicate_page_declares_canonical_to_main(self):
        best = self._p(10, "Organizador de huevos", images=[{"url": "https://x/1.jpg"}, {"url": "https://x/2.jpg"}])
        dup = self._p(11, "Organizador de Huevos")
        call_command("consolidate_seo", "--apply", stdout=StringIO())
        html = self.client.get(f"/producto/{dup.slug}/").content.decode()
        self.assertIn(f'<link rel="canonical" href="http://testserver/producto/{best.slug}/"', html)


class TemplateCommentTests(SimpleTestCase):
    def test_no_multiline_hash_comments(self):
        """{# … #} de Django es de UNA línea: si se parte, se imprime como texto
        en la página (pasó en el <head> y en las tarjetas de producto)."""
        import re
        from django.conf import settings

        offenders = []
        for base in settings.TEMPLATES[0]["DIRS"]:
            for path in Path(base).rglob("*.html"):
                text = path.read_text(encoding="utf-8")
                for match in re.finditer(r"\{#(.*?)#\}", text, re.S):
                    if "\n" in match.group(1):
                        offenders.append(f"{path.name}:{text[:match.start()].count(chr(10)) + 1}")
                if re.search(r"\{#(?![^\n]*#\})", text):
                    offenders.append(f"{path.name}: {{# sin cerrar en la misma línea")
        self.assertEqual(offenders, [])


class HideCheapProductsTests(TestCase):
    def test_hides_only_active_unlocked_products_below_the_floor(self):
        from io import StringIO

        from django.core.management import call_command

        cat = Category.objects.create(dropi_id="store:otros", name="Otros")
        cheap = Product.objects.create(dropi_id=9101, name="Borrador", slug="borrador", category=cat,
                                       price=Decimal("19"), cost=Decimal("6"), is_active=True)
        locked = Product.objects.create(dropi_id=9102, name="Pila", slug="pila", category=cat,
                                        price=Decimal("19"), cost=Decimal("6"), is_active=True, price_locked=True)
        fine = Product.objects.create(dropi_id=9103, name="Cepillo", slug="cepillo", category=cat,
                                      price=Decimal("499"), cost=Decimal("170"), is_active=True)
        call_command("hide_cheap_products", stdout=StringIO())
        cheap.refresh_from_db()
        self.assertTrue(cheap.is_active)  # simulación no escribe
        sold = Product.objects.create(dropi_id=9104, name="Lápiz", slug="lapiz", category=cat,
                                      price=Decimal("19"), cost=Decimal("6"), is_active=True)
        from orders.models import Order
        Order.objects.create(name="A", surname="B", email="a@b.co", phone="3000000000", address="x", city="Cali",
                             state="VAC", payment_method=Order.PAYMENT_COD, total=1, items=[{"product_id": sold.pk}])
        call_command("hide_cheap_products", "--apply", stdout=StringIO())
        sold.refresh_from_db()
        self.assertTrue(sold.is_active)  # vendido: protegido
        for p in (cheap, locked, fine):
            p.refresh_from_db()
        self.assertEqual((cheap.is_active, cheap.inactive_reason), (False, "precio_bajo"))
        self.assertTrue(locked.is_active)
        self.assertTrue(fine.is_active)


class SyncPriorityStockTests(TestCase):
    def setUp(self):
        from orders.models import Order

        cat = Category.objects.create(dropi_id="store:salud_bienestar", name="Salud y Bienestar")
        self.agotado = Product.objects.create(dropi_id=9201, name="Selvia", slug="selvia", category=cat,
                                              price=Decimal("56900"), cost=Decimal("24000"), stock=0, is_active=True)
        self.privado = Product.objects.create(dropi_id=9202, name="Láser", slug="laser", category=cat,
                                              price=Decimal("39900"), cost=Decimal("12900"), stock=824,
                                              is_active=False, inactive_reason="no_existe")
        self.vacio = Product.objects.create(dropi_id=9203, name="Gotas", slug="gotas", category=cat,
                                            price=Decimal("39900"), cost=Decimal("12900"), stock=5, is_active=True)
        self.no_vendido = Product.objects.create(dropi_id=9204, name="Otro", slug="otro", category=cat,
                                                 price=Decimal("39900"), cost=Decimal("12900"), stock=0,
                                                 is_active=True)
        Order.objects.create(
            name="A", surname="B", email="a@b.co", phone="3000000000", address="x", city="Cali", state="VAC",
            payment_method=Order.PAYMENT_COD, total=1,
            items=[{"product_id": p.pk} for p in (self.agotado, self.privado, self.vacio)],
        )

    def _detail(self, product_id, timeout=60):
        stock = {9201: 451, 9202: 824, 9203: 0}[product_id]
        return {"objects": {"id": product_id, "active": True, "privated_product": product_id == 9202,
                            "warehouse_product": [{"stock": stock}]}}

    def _run(self, *args):
        from unittest.mock import patch

        with patch("catalog.management.commands.sync_priority_stock.DropiClient") as client:
            client.return_value.get_product.side_effect = self._detail
            call_command("sync_priority_stock", "--delay", "0", *args, stdout=StringIO())
            return client.return_value.get_product

    def test_updates_stock_of_sold_products_only(self):
        calls = self._run()
        self.assertNotIn(9204, [c.args[0] for c in calls.call_args_list])
        for p in (self.agotado, self.privado, self.vacio):
            p.refresh_from_db()
        self.assertEqual((self.agotado.stock, self.agotado.is_active), (451, True))
        # Privado en Dropi: no se puede pedir, sigue despublicado.
        self.assertEqual((self.privado.is_active, self.privado.inactive_reason), (False, "no_existe"))
        # Stock 0: la ficha sigue en línea como agotada (nunca 410).
        self.assertEqual((self.vacio.stock, self.vacio.is_active), (0, True))

    def test_reactivates_auto_deactivated_sellable_product(self):
        Product.objects.filter(pk=self.agotado.pk).update(is_active=False, inactive_reason="sin_stock")
        self._run()
        self.agotado.refresh_from_db()
        self.assertEqual((self.agotado.is_active, self.agotado.inactive_reason, self.agotado.stock), (True, "", 451))

    def test_dry_run_writes_nothing(self):
        self._run("--dry-run")
        self.agotado.refresh_from_db()
        self.assertEqual(self.agotado.stock, 0)

    def test_retries_same_product_after_rate_limit(self):
        from unittest.mock import patch

        from dropi_client import DropiAPIError

        calls = []

        def flaky(product_id, timeout=60):
            calls.append(product_id)
            if calls.count(product_id) == 1 and product_id == 9201:
                raise DropiAPIError("429 Client Error: Too Many Requests")
            return self._detail(product_id)

        with patch("catalog.management.commands.sync_priority_stock.DropiClient") as client, \
                patch("catalog.management.commands.sync_priority_stock.RATE_LIMIT_SLEEP", 0):
            client.return_value.get_product.side_effect = flaky
            call_command("sync_priority_stock", "--delay", "0", stdout=StringIO())
        self.agotado.refresh_from_db()
        self.assertEqual(self.agotado.stock, 451)
