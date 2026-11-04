from decimal import Decimal

from django.test import TestCase

from catalog.inventory import get_available_stock, variation_stock
from catalog.models import Category, Product


class InventoryTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(dropi_id="c1", name="Cat")
        self.product = Product.objects.create(
            dropi_id=1,
            name="P",
            slug="p",
            price=Decimal("10"),
            stock=10,
            category=cat,
            is_active=True,
            variants=[
                {
                    "id": 99,
                    "attribute_values": [{"value": "Rojo"}],
                    "warehouse_product_variation": [{"stock": 3}],
                }
            ],
        )

    def test_variation_stock(self):
        self.assertEqual(variation_stock(self.product, 99), 3)
        self.assertEqual(get_available_stock(self.product, 99), 3)
        self.assertEqual(get_available_stock(self.product, None), 10)

    def test_variant_with_zero_warehouse_stock_is_not_masked_by_aggregate(self):
        # A variant whose own warehouses sum to zero must report zero, even
        # though the product-level aggregate stock (shared across all colors/
        # sizes) is still positive — Dropi rejects the order creation in
        # exactly this case ("Producto no posee stock en ninguna de sus
        # bodegas"), so checkout must catch it before submitting, not after.
        product = Product.objects.create(
            dropi_id=2,
            name="Variable product",
            slug="variable-product",
            price=Decimal("10"),
            stock=11959,
            category=self.product.category,
            is_active=True,
            variants=[
                {
                    "id": 555,
                    "attribute_values": [{"value": "Beigge / L"}],
                    "warehouse_product_variation": [{"stock": 0}],
                }
            ],
        )
        self.assertEqual(variation_stock(product, 555), 0)
        self.assertEqual(get_available_stock(product, 555), 0)

    def test_attribute_group_variant_falls_back_to_aggregate_stock(self):
        # Attribute-group style variants carry no stock breakdown of their
        # own, so falling back to the product aggregate is the only signal
        # available (unlike the individual-SKU case above).
        product = Product.objects.create(
            dropi_id=3,
            name="Attribute group product",
            slug="attribute-group-product",
            price=Decimal("10"),
            stock=7,
            category=self.product.category,
            is_active=True,
            variants=[{"id": 42, "description": "Color", "values": [{"id": 43, "value": "Azul"}]}],
        )
        self.assertEqual(variation_stock(product, 43), 7)
