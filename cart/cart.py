from decimal import Decimal

from django.conf import settings

from catalog.inventory import get_available_stock, variation_label
from catalog.models import Product

from .suppliers import validate_supplier_for_add


class Cart:
    """Session-based shopping cart."""

    def __init__(self, request):
        # Leer no escribe: antes cada página guardaba un carrito vacío en la
        # sesión, creando una sesión (y una fila en la base de datos) por cada
        # visita, bots incluidos, y una cookie que impedía servir la página
        # desde caché. La sesión se crea al guardar el primer producto.
        self.session = request.session
        self.cart = self.session.get(settings.CART_SESSION_ID) or {}

    def save(self):
        self.session[settings.CART_SESSION_ID] = self.cart
        self.session.modified = True

    def add(
        self,
        product: Product,
        quantity: int = 1,
        override_qty: bool = False,
        variation_id: int | None = None,
    ) -> tuple[bool, str, str]:
        """
        Add or update a cart line. Returns (success, error_message, warning_message).
        """
        available = get_available_stock(product, variation_id)
        if available <= 0:
            return False, f"«{product.name}» no tiene stock disponible.", ""

        cart_key = f"{product.pk}_{variation_id}" if variation_id else str(product.pk)
        is_new_line = cart_key not in self.cart
        warning = ""

        if is_new_line:
            allowed, err, warn = validate_supplier_for_add(self.cart, product, variation_id)
            if not allowed:
                return False, err, ""
            warning = warn

        if is_new_line:
            self.cart[cart_key] = {
                "quantity": 0,
                "price": str(product.price),
                "cost": str(product.cost),
                "name": product.name,
                "display_name": product.shown_name,
                "slug": product.slug,
                "image": product.main_image,
                "dropi_id": product.dropi_id,
                "supplier_id": product.supplier_id,
                "local_id": product.pk,
                "stock": available,
                "variation_id": variation_id,
                "variation_label": variation_label(product, variation_id),
            }
        else:
            self.cart[cart_key]["stock"] = available
            self.cart[cart_key]["price"] = str(product.price)

        new_qty = quantity if override_qty else self.cart[cart_key]["quantity"] + quantity
        if new_qty > available:
            return False, f"Solo hay {available} unidades disponibles de «{product.shown_name}».", ""

        self.cart[cart_key]["quantity"] = new_qty
        self.save()
        return True, "", warning

    def refresh_from_db(self) -> list[str]:
        """Revalidate price/stock from DB. Returns list of error messages."""
        errors: list[str] = []
        pk_set = {int(k.split("_")[0]) for k in self.cart}
        products = {p.pk: p for p in Product.objects.filter(pk__in=pk_set, is_active=True)}

        for cart_key in list(self.cart.keys()):
            line = self.cart[cart_key]
            product = products.get(line.get("local_id") or int(cart_key.split("_")[0]))
            if not product:
                del self.cart[cart_key]
                errors.append("Se eliminó un producto que ya no está disponible.")
                continue

            vid = line.get("variation_id")
            available = get_available_stock(product, vid)
            line["price"] = str(product.price)
            line["cost"] = str(product.cost)
            line["stock"] = available
            line["variation_label"] = variation_label(product, vid)

            if available <= 0:
                name = line.get("name", product.name)
                del self.cart[cart_key]
                errors.append(f"«{name}» se agotó y fue eliminado del carrito.")
            elif line["quantity"] > available:
                line["quantity"] = available
                errors.append(f"Se ajustó la cantidad de «{product.name}» a {available} unidades.")

        if errors:
            self.save()
        return errors

    def remove(self, product: Product = None, variation_id: int = None, cart_key: str = None):
        if cart_key is None and product is not None:
            product_id = str(product.pk)
            cart_key = f"{product_id}_{variation_id}" if variation_id else product_id
        if cart_key and cart_key in self.cart:
            del self.cart[cart_key]
            self.save()

    def update_quantity(self, cart_key: str, quantity: int) -> bool:
        """Set quantity for a cart line. Returns False if key missing."""
        if cart_key not in self.cart:
            return False
        if quantity < 1:
            del self.cart[cart_key]
        else:
            self.cart[cart_key]["quantity"] = quantity
        self.save()
        return True

    def get_line(self, cart_key: str) -> dict | None:
        return self.cart.get(cart_key)

    def __iter__(self):
        # Cart keys are either "pk" or "pk_variation_id"
        pk_set = set()
        for key in self.cart.keys():
            pk_set.add(int(key.split("_")[0]))
        products = {p.pk: p for p in Product.objects.filter(pk__in=pk_set)}
        for cart_key, raw in self.cart.items():
            item = raw.copy()
            item["cart_key"] = cart_key
            product = products.get(item.get("local_id") or int(cart_key.split("_")[0]))
            if product:
                item["product"] = product
            unit_price = Decimal(item["price"])
            unit_cost = Decimal(item.get("cost") or "0")
            item["price"] = unit_price
            item["cost"] = unit_cost
            item["unit_price"] = unit_price
            item["total_price"] = unit_price * item["quantity"]
            item["subtotal"] = item["total_price"]
            item["line_margin"] = (unit_price - unit_cost) * item["quantity"]
            if not item.get("variation_label") and item.get("variation_id"):
                item["variation_label"] = variation_label(product, item["variation_id"]) if product else ""
            yield item

    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())

    def get_total(self) -> Decimal:
        return sum(Decimal(item["price"]) * item["quantity"] for item in self.cart.values())

    def clear(self):
        self.session.pop(settings.CART_SESSION_ID, None)
        self.session.modified = True
        self.cart = {}
