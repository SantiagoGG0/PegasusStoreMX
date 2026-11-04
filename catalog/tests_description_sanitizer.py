# pylint: disable=no-member
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product
from catalog.services.description_sanitizer import (
    find_description_issues,
    sanitize_product_description,
)
from catalog.services.dropi_import import upsert_product


class DescriptionSanitizerTests(TestCase):
    def test_removes_drive_telegram_and_supplier_warranty(self):
        raw = """
        <p>Producto resistente para uso diario.</p>
        <p>Recursos adicionales en Google Drive: https://drive.google.com/file/d/abc</p>
        <p>Unete al canal de Telegram: https://t.me/proveedor</p>
        <p>Garantia solo por defectos de fabrica con empaque original.</p>
        """

        issues = set(find_description_issues(raw))
        cleaned = sanitize_product_description(raw)

        self.assertIn("drive_link", issues)
        self.assertIn("telegram_link", issues)
        self.assertIn("supplier_warranty", issues)
        self.assertIn("<p>Producto resistente para uso diario.</p>", cleaned)
        self.assertNotIn("drive.google", cleaned)
        self.assertNotIn("Telegram", cleaned)
        self.assertNotIn("Garantia", cleaned)

    def test_removes_youtube_whatsapp_group_and_supplier_phone(self):
        raw = """
        Incluye cable de carga.
        Mira el video https://youtube.com/shorts/abcdefghijk
        Comunidad WhatsApp https://chat.whatsapp.com/invite
        Ventas al por mayor 3008725058
        """

        issues = set(find_description_issues(raw))
        cleaned = sanitize_product_description(raw)

        self.assertIn("youtube_link", issues)
        self.assertIn("whatsapp_group", issues)
        self.assertIn("supplier_phone", issues)
        self.assertEqual(cleaned, "<p>Incluye cable de carga.</p>")

    def test_converts_editor_json_to_clean_paragraphs(self):
        raw = (
            '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text",'
            '"text":"Primera linea util"}]},{"type":"paragraph","content":[{"type":"text",'
            '"text":"Canal proveedor https://t.me/test"}]},{"type":"paragraph","content":'
            '[{"type":"text","text":"Segunda linea util"}]}]}'
        )

        issues = set(find_description_issues(raw))
        cleaned = sanitize_product_description(raw)

        self.assertIn("json_doc", issues)
        self.assertEqual(
            cleaned,
            "<p>Primera linea util</p>\n<p>Segunda linea util</p>",
        )


class DropiImportDescriptionSanitizerTests(TestCase):
    def test_upsert_product_sanitizes_description_before_save(self):
        product, _ = upsert_product(
            {
                "id": 991001,
                "name": "Producto Dropi Sanitizado",
                "description": "Descripcion util\nTelegram proveedor https://t.me/test",
                "sale_price": 10000,
                "suggested_price": 30000,
                "warehouse_product": [{"stock": 10}],
                "images": [{"url": "https://example.com/product.jpg"}],
            }
        )

        product.refresh_from_db()
        self.assertEqual(product.description, "<p>Descripcion util</p>")


class AuditProductDescriptionsCommandTests(TestCase):
    def test_summary_reports_affected_products_without_fixing(self):
        Product.objects.create(
            dropi_id=991101,
            name="Producto Auditado",
            description="Texto util\nGarantia proveedor https://example.com",
            price=20000,
            stock=1,
        )

        output = StringIO()
        call_command("audit_product_descriptions", "--summary-only", stdout=output)

        text = output.getvalue()
        self.assertIn("Escaneados: 1", text)
        self.assertIn("Afectados: 1", text)
        self.assertIn("supplier_warranty: 1", text)

    def test_fix_updates_only_affected_descriptions(self):
        product = Product.objects.create(
            dropi_id=991102,
            name="Producto Limpieza",
            description="Texto util\nCatalogo proveedor https://drive.google.com/test",
            price=20000,
            stock=1,
        )

        call_command("audit_product_descriptions", "--fix", "--summary-only")

        product.refresh_from_db()
        self.assertEqual(product.description, "<p>Texto util</p>")

    def test_fix_writes_backup_file_before_updating_descriptions(self):
        product = Product.objects.create(
            dropi_id=991103,
            name="Producto Backup",
            description="Texto util\nTelegram proveedor https://t.me/test",
            price=20000,
            stock=1,
        )

        with TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "descriptions-backup.jsonl"
            call_command(
                "audit_product_descriptions",
                "--fix",
                "--summary-only",
                "--backup-file",
                str(backup_path),
            )

            backup_content = backup_path.read_text(encoding="utf-8")

        product.refresh_from_db()
        self.assertEqual(product.description, "<p>Texto util</p>")
        self.assertIn('"id": %s' % product.pk, backup_content)
        self.assertIn('"dropi_id": 991103', backup_content)
        self.assertIn("Telegram proveedor", backup_content)

    def test_restore_reverts_descriptions_from_backup_file(self):
        product = Product.objects.create(
            dropi_id=991104,
            name="Producto Restore",
            description="Texto original\nGarantia proveedor https://example.com",
            price=20000,
            stock=1,
        )

        with TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "descriptions-backup.jsonl"
            call_command(
                "audit_product_descriptions",
                "--fix",
                "--summary-only",
                "--backup-file",
                str(backup_path),
            )
            product.refresh_from_db()
            self.assertEqual(product.description, "<p>Texto original</p>")

            call_command("audit_product_descriptions", "--restore", str(backup_path))

        product.refresh_from_db()
        self.assertEqual(
            product.description,
            "Texto original\nGarantia proveedor https://example.com",
        )


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProductDetailAdultNoticeTests(TestCase):
    def test_bienestar_intimo_product_shows_adult_notice(self):
        category = Category.objects.create(
            dropi_id="store:bienestar_intimo",
            name="Bienestar Intimo",
        )
        product = Product.objects.create(
            dropi_id=991201,
            name="Producto Adulto",
            description="<p>Descripcion limpia</p>",
            category=category,
            price=50000,
            stock=5,
            is_active=True,
            slug="producto-adulto",
        )

        response = self.client.get(reverse("catalog:detail", kwargs={"slug": product.slug}))

        self.assertContains(response, "Producto para adultos +18")
        self.assertContains(response, "Compra discreta")
        self.assertContains(response, "Mantener fuera del alcance de menores")
