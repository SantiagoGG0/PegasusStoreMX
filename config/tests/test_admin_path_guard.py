from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.admin_path import (
    has_admin_path_bypass_markers,
    normalize_request_path,
    should_block_admin_path,
)
from config.middleware import AdminPathGuardMiddleware


class AdminPathNormalizationTests(SimpleTestCase):
    def test_normalize_collapses_dot_and_double_slash(self):
        self.assertEqual(normalize_request_path("//admin//"), "/admin/")
        self.assertEqual(normalize_request_path("/./admin/./"), "/admin/")
        self.assertIn(normalize_request_path("/admin/."), ("/admin", "/admin/"))

    def test_normalize_strips_semicolon_matrix(self):
        self.assertEqual(normalize_request_path("/admin/.;/"), "/admin")

    def test_normalize_decodes_percent_encoding(self):
        self.assertEqual(normalize_request_path("/admin%20"), "/admin")


class AdminPathBypassMarkerTests(SimpleTestCase):
    def test_detects_image_tricks(self):
        for path in (
            "/admin/.",
            "//admin//",
            "/./admin/./",
            "/admin/.;/",
            "/admin%20",
        ):
            with self.subTest(path=path):
                self.assertTrue(has_admin_path_bypass_markers(path))

    def test_clean_path_has_no_markers(self):
        self.assertFalse(has_admin_path_bypass_markers("/panel-pegasus-interno/"))


class AdminPathBlockLogicTests(SimpleTestCase):
    admin_slug = "panel-pegasus-interno"

    def test_legacy_admin_always_blocked(self):
        for path in ("/admin", "/admin/", "/admin/login/"):
            with self.subTest(path=path):
                self.assertTrue(should_block_admin_path(path, self.admin_slug))

    def test_legacy_bypass_tricks_blocked(self):
        for path in (
            "/admin/.",
            "//admin//",
            "/./admin/./",
            "/admin/.;/",
            "/admin%20",
        ):
            with self.subTest(path=path):
                self.assertTrue(should_block_admin_path(path, self.admin_slug))

    def test_canonical_custom_admin_allowed(self):
        self.assertFalse(
            should_block_admin_path("/panel-pegasus-interno/", self.admin_slug)
        )
        self.assertFalse(
            should_block_admin_path(
                "/panel-pegasus-interno/login/", self.admin_slug
            )
        )

    def test_custom_admin_bypass_tricks_blocked(self):
        for path in (
            "/panel-pegasus-interno/.",
            "//panel-pegasus-interno//",
            "/./panel-pegasus-interno/./",
            "/panel-pegasus-interno/.;/",
            "/panel-pegasus-interno%20",
        ):
            with self.subTest(path=path):
                self.assertTrue(should_block_admin_path(path, self.admin_slug))

    def test_catalog_paths_not_blocked(self):
        self.assertFalse(should_block_admin_path("/", self.admin_slug))
        self.assertFalse(should_block_admin_path("/carrito/", self.admin_slug))


@override_settings(ADMIN_URL="panel-pegasus-interno/")
class AdminPathGuardMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AdminPathGuardMiddleware(
            get_response=lambda request: HttpResponse("OK")
        )

    def _build_request(self, path: str):
        request = self.factory.get("/")
        request.path = path
        request.path_info = path
        request.META["RAW_URI"] = path
        return request

    def _assert_blocked(self, path: str) -> None:
        response = self.middleware(self._build_request(path))
        self.assertEqual(response.status_code, 403, msg=path)

    def _assert_allowed(self, path: str) -> None:
        response = self.middleware(self._build_request(path))
        self.assertEqual(response.status_code, 200, msg=path)

    def test_middleware_blocks_legacy_admin_tricks(self):
        for path in (
            "/admin",
            "/admin/",
            "/admin/.",
            "//admin//",
            "/./admin/./",
            "/admin/.;/",
            "/admin%20",
        ):
            with self.subTest(path=path):
                self._assert_blocked(path)

    def test_middleware_blocks_custom_admin_tricks(self):
        slug = settings.ADMIN_URL.strip("/")
        for path in (
            f"/{slug}/.",
            f"//{slug}//",
            f"/./{slug}/./",
            f"/{slug}/.;/",
            f"/{slug}%20",
        ):
            with self.subTest(path=path):
                self._assert_blocked(path)

    def test_middleware_allows_canonical_admin_and_public(self):
        slug = settings.ADMIN_URL.strip("/")
        self._assert_allowed(f"/{slug}/")
        self._assert_allowed("/robots.txt")
