import json
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import Category, Product
from catalog.services.gallery_sync import GalleryResult


def listing_raw(dropi_id, stock=10, cost=20_000, suggested=60_000):
    return {
        "id": dropi_id, "name": f"Producto {dropi_id}", "sale_price": cost, "suggested_price": suggested,
        "gallery": [{"urlS3": f"colombia/products/{dropi_id}/main.jpg"}],
        "warehouse_product": [{"stock": stock}],
    }


@override_settings(CATALOG_MIN_IMAGES=2, GALLERY_ON_VIEW=False, DROPI_READ_TOKENS=["token-1"])
class CatalogWorkerTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(dropi_id="store:otros", name="Otros")
        self.state_file = Path(tempfile.mkdtemp()) / "state.json"
        self.pages = {}            # cursor -> lista de productos del listado
        self.galleries = {}        # dropi_id -> GalleryResult

    def _product(self, dropi_id, **kwargs):
        defaults = dict(
            name=f"P{dropi_id}", slug=f"p{dropi_id}", category=self.cat, cost=Decimal("20000"),
            price=Decimal("59900"), stock=5, is_active=True, suggested_price=Decimal("60000"),
            images=[{"url": "https://cdn/1.jpg"}],
        )
        defaults.update(kwargs)
        return Product.objects.create(dropi_id=dropi_id, **defaults)

    def _gallery(self, dropi_id, n_images=3, stock=10, found=True):
        self.galleries[dropi_id] = GalleryResult(
            dropi_id=dropi_id, found=found, stock=stock, cost=Decimal("20000"), suggested=Decimal("60000"),
            images=[{"url": f"https://cdn/{dropi_id}/{i}.jpg"} for i in range(n_images)],
        )

    def _run(self, steps, *extra_args):
        """Corre el worker exactamente `steps` requests (cada request avanza el reloj)."""
        # 1.ª lectura: cálculo del deadline (= steps min); luego una por vuelta: 0, 1, 2… min.
        clock = iter([0, *range(0, 10_000)])

        def fetch_page(client, cursor, page_size, category, stdout=None):
            return self.pages.get(cursor, [])

        def fetch_gallery(client, session, dropi_id, verify=True, limiter=None):
            return self.galleries.get(dropi_id, GalleryResult(dropi_id=dropi_id, found=False))

        with mock.patch("catalog.management.commands.catalog_worker._fetch_page", side_effect=fetch_page), \
             mock.patch("catalog.management.commands.catalog_worker.fetch_gallery", side_effect=fetch_gallery), \
             mock.patch("catalog.management.commands.catalog_worker.DropiClient"), \
             mock.patch("catalog.management.commands.catalog_worker.RateLimiter", **{"return_value.interval": 10.0}), \
             mock.patch("catalog.management.commands.catalog_worker.time.monotonic", side_effect=lambda: next(clock) * 60):
            call_command(
                "catalog_worker", "--max-minutes", str(steps), "--listing-every", "2",
                "--state-file", str(self.state_file), *extra_args, stdout=StringIO(), stderr=StringIO(),
            )

    def test_listing_updates_stock_and_creates_new_pending_product(self):
        existing = self._product(1, stock=5)
        self.pages = {0: [listing_raw(1, stock=42), listing_raw(2)]}
        self._run(steps=2)

        existing.refresh_from_db()
        self.assertEqual(existing.stock, 42)
        new = Product.objects.get(dropi_id=2)
        self.assertFalse(new.is_active)
        self.assertEqual(new.inactive_reason, "sin_imagenes")
        self.assertGreater(new.price, 0)
        self.assertEqual(json.loads(self.state_file.read_text())["cursor"], 2)

    def test_new_product_published_after_gallery_with_enough_images(self):
        self.pages = {0: [listing_raw(2), listing_raw(3)]}
        self._gallery(2, n_images=3)
        self._gallery(3, n_images=1)   # menos de CATALOG_MIN_IMAGES
        self._run(steps=6)

        self.assertTrue(Product.objects.get(dropi_id=2).is_active)
        self.assertEqual(len(Product.objects.get(dropi_id=2).images), 3)
        self.assertFalse(Product.objects.get(dropi_id=3).is_active)

    def test_end_of_cycle_deactivates_products_dropi_no_longer_lists(self):
        for i in range(1, 5):
            self._product(i)
            self._gallery(i)
        self.pages = {0: [listing_raw(1), listing_raw(2), listing_raw(3)]}   # el 4 ya no aparece
        self._run(steps=10)

        self.assertFalse(Product.objects.get(dropi_id=4).is_active)
        self.assertEqual(Product.objects.get(dropi_id=4).inactive_reason, "no_existe")
        self.assertTrue(Product.objects.get(dropi_id=1).is_active)
        self.assertEqual(json.loads(self.state_file.read_text())["cursor"], 0)   # vuelta nueva

    def test_incomplete_cycle_deactivates_nothing(self):
        for i in range(1, 5):
            self._product(i)
            self._gallery(i)
        self.pages = {0: [listing_raw(1)]}    # Dropi devolvió 1 de 4 activos
        self._run(steps=10)
        self.assertEqual(Product.objects.filter(is_active=True).count(), 4)

    def test_resumes_from_saved_cursor(self):
        self._product(1)
        self._product(2, stock=1)
        self.state_file.write_text(json.dumps({"cursor": 40, "seen": [1], "cycle_started": "2026-10-06T00:00"}))
        self.pages = {40: [listing_raw(2, stock=99)]}
        self._run(steps=2)

        self.assertEqual(Product.objects.get(dropi_id=2).stock, 99)
        state = json.loads(self.state_file.read_text())
        self.assertEqual(state["cursor"], 41)
        self.assertEqual(sorted(state["seen"]), [1, 2])

    def test_network_error_does_not_stop_the_worker(self):
        self._product(1, stock=5)
        self.pages = {0: [listing_raw(1, stock=77)]}
        calls = {"n": 0}
        real_queue = __import__("catalog.services.gallery_sync", fromlist=["gallery_queue"]).gallery_queue

        def flaky_queue(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                from django.db import OperationalError
                raise OperationalError("server closed the connection unexpectedly")
            return real_queue(*args, **kwargs)

        with mock.patch("catalog.management.commands.catalog_worker.gallery_queue", side_effect=flaky_queue), \
             mock.patch("catalog.management.commands.catalog_worker.time.sleep"):
            self._run(steps=4)
        self.assertEqual(Product.objects.get(dropi_id=1).stock, 77)

    @override_settings(DROPI_READ_TOKENS=["token-1", "token-2"])
    def test_second_token_only_fetches_galleries_of_its_share(self):
        products = [self._product(i, gallery_synced_at=None) for i in range(1, 7)]
        for p in products:
            self._gallery(p.dropi_id)
        self.pages = {0: [listing_raw(99)]}
        with mock.patch("catalog.management.commands.catalog_worker.time.sleep"):
            self._run(10, "--token-index", "1")

        synced = {p.pk % 2 for p in Product.objects.exclude(gallery_synced_at=None)}
        self.assertEqual(synced, {1})                              # solo su porción
        self.assertFalse(Product.objects.filter(dropi_id=99).exists())   # no recorre el listado
        self.assertFalse(self.state_file.exists())

