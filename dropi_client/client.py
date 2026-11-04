import base64
import json
import logging

import requests
from django.conf import settings

from .exceptions import DropiAPIError

logger = logging.getLogger(__name__)


def _extract_integration_url(token: str) -> str:
    """Decode the JWT payload (no signature check needed — just reading claims)."""
    try:
        payload_b64 = token.split(".")[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        url = payload.get("integration_url", "")
        if url and not url.startswith("http"):
            url = "https://" + url
        return url
    except Exception:
        return ""


class DropiClient:
    """
    Wrapper para la API de Dropi México.
    Base URL: https://api.dropi.mx/integrations/
    Auth: header 'dropi-integration-key'
    Dropi validates requests via User-Agent matching the integration_url in the JWT.
    """

    def __init__(self, token: str | None = None):
        self.base_url = settings.DROPI_BASE_URL.rstrip("/") + "/"
        self.token = token or settings.DROPI_TOKEN
        integration_url = _extract_integration_url(self.token)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "dropi-integration-key": self.token,
                "Content-Type": "application/json;charset=UTF-8",
                "User-Agent": f"WordPress/6.5; {integration_url}",
            }
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get(self, path: str, params: dict = None, timeout: float = 60) -> dict:
        url = self.base_url + path.lstrip("/")
        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DropiAPIError(str(exc)) from exc
        return self._parse(resp)

    def _post(self, path: str, payload: dict) -> dict:
        url = self.base_url + path.lstrip("/")
        try:
            resp = self.session.post(url, json=payload, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DropiAPIError(str(exc)) from exc
        return self._parse(resp)

    def _put(self, path: str, payload: dict) -> dict:
        url = self.base_url + path.lstrip("/")
        try:
            resp = self.session.put(url, json=payload, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DropiAPIError(str(exc)) from exc
        return self._parse(resp)

    @staticmethod
    def _parse(resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except ValueError as exc:
            raise DropiAPIError("Respuesta no JSON de Dropi") from exc
        if not data.get("isSuccess", True):
            msg = data.get("message", "Error desconocido de Dropi")
            # Include response data for debugging stock issues
            if "stock" in msg.lower() or "bodega" in msg.lower():
                logger.error("Dropi stock validation failed. Response: %s", data)
            raise DropiAPIError(msg)
        return data

    # ── Products ─────────────────────────────────────────────────────────────

    def get_products(
        self,
        page: int = 0,
        page_size: int = 20,
        category: str = "",
        keywords: str = "",
        warehouse_id: str = "",
    ) -> dict:
        """
        POST products/index
        Returns the API response dict. Key: objects (list of products) and total.
        """
        payload = {
            "startData": page * page_size,
            "pageSize": page_size,
            "order_type": "ASC",
            "order_by": "name",
            "keywords": keywords,
            "active": True,
            "no_count": True,
            "integration": True,
            "get_stock": True,
            # Sin "userVerified": en Dropi México solo un proveedor tiene esa marca
            # y el catálogo quedaba en ~34 productos (con él, 5.000-10.000). La
            # calidad la filtran las reglas propias del importador.
            "stockmayor": 1,
            "notNulldescription": True,
        }
        if category:
            payload["category"] = category
        if warehouse_id:
            payload["warehouse_id"] = warehouse_id
        return self._post("products/index", payload)

    def get_product(self, product_id: int, timeout: float = 60) -> dict:
        """GET products/v2/{id}"""
        return self._get(f"products/v2/{product_id}", timeout=timeout)

    # ── Categories ───────────────────────────────────────────────────────────

    def get_categories(self) -> dict:
        """GET categories/"""
        return self._get("categories/")

    # ── Warehouses ───────────────────────────────────────────────────────────

    def get_warehouses(self) -> dict:
        """GET warehouses/"""
        return self._get("warehouses/")

    # ── Orders ───────────────────────────────────────────────────────────────

    def create_order(self, order_data: dict) -> dict:
        """
        POST orders/myorders
        order_data should be a fully formed Dropi order payload.
        Returns the response dict (contains dropi_order_id in objects).
        """
        return self._post("orders/myorders", order_data)

    def get_order(self, dropi_order_id: str) -> dict:
        """
        GET orders/myorders/{id}
        Returns current order data from Dropi (status, guide number, carrier, etc.).
        """
        return self._get(f"orders/myorders/{dropi_order_id}")

    def cancel_order(self, dropi_order_id: str, shop_order_id: int | None = None) -> dict:
        """
        Attempt to cancel an order in Dropi. Tries known endpoint patterns;
        raises DropiAPIError if none succeed (caller may fall back to local cancel).
        """
        if not dropi_order_id:
            raise DropiAPIError("Sin ID de orden Dropi para cancelar")

        candidates = [
            ("PUT", f"orders/myorders/{dropi_order_id}", {"status": "CANCELADO"}),
            ("PUT", f"orders/myorders/{dropi_order_id}", {"status": "CANCELADO", "shop_order_id": shop_order_id}),
            ("POST", "orders/cancel", {"order_id": dropi_order_id, "shop_order_id": shop_order_id}),
            ("POST", f"orders/myorders/{dropi_order_id}/cancel", {}),
        ]
        last_error = None
        for method, path, payload in candidates:
            try:
                if method == "PUT":
                    return self._put(path, payload)
                return self._post(path, payload)
            except DropiAPIError as exc:
                last_error = exc
                logger.debug("Dropi cancel attempt failed %s %s: %s", method, path, exc)
        raise DropiAPIError(str(last_error or "No se pudo cancelar en Dropi"))

    # ── Import list ──────────────────────────────────────────────────────────

    def mark_imported(self, dropi_product_id: int, local_id: int, slug: str) -> dict:
        """PUT importlist/importstore/1 — marks a product as imported."""
        payload = {
            "products_id": dropi_product_id,
            "imported_to_store": True,
            "woocomerse_id": local_id,
            "woocomerse_url": slug,
        }
        return self._put("importlist/importstore/1", payload)
