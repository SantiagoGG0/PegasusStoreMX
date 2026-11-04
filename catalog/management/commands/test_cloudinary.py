"""
Management command to verify Cloudinary connectivity and storage backend.

Run from DO Console:
    python manage.py test_cloudinary
"""
import io

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test Cloudinary storage backend and upload connectivity"

    def handle(self, *args, **options):
        # 1. Show which backend is active
        # default_storage is a lazy DefaultStorage proxy — must check _wrapped or settings
        from django.conf import settings as django_settings
        import os

        configured = getattr(django_settings, 'DEFAULT_FILE_STORAGE', 'django.core.files.storage.FileSystemStorage')
        self.stdout.write(f"DEFAULT_FILE_STORAGE setting: {configured}")
        self.stdout.write(f"USE_CLOUDINARY env raw: {repr(os.environ.get('USE_CLOUDINARY'))}")

        # Force lazy proxy to initialize
        try:
            _ = default_storage._wrapped
            actual = f"{type(default_storage._wrapped).__module__}.{type(default_storage._wrapped).__name__}"
        except Exception:
            actual = configured
        self.stdout.write(f"Actual storage backend: {actual}")

        is_cloudinary = "cloudinary" in actual.lower() or "cloudinary" in configured.lower()
        if is_cloudinary:
            self.stdout.write(self.style.SUCCESS("Cloudinary backend ACTIVE"))
        else:
            self.stdout.write(self.style.ERROR(f"NOT cloudinary — using: {actual}"))
            self.stdout.write("Check USE_CLOUDINARY env var and CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET")
            return

        # 2. Try test upload
        self.stdout.write("Testing upload...")
        test_content = b"cloudinary_test_ok"
        test_file = io.BytesIO(test_content)
        test_file.name = "health_check.txt"

        try:
            path = default_storage.save("test/health_check.txt", test_file)
            url = default_storage.url(path)
            self.stdout.write(self.style.SUCCESS(f"Upload OK → {url}"))
            default_storage.delete(path)
            self.stdout.write(self.style.SUCCESS("Delete OK"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Upload FAILED: {exc}"))
            return

        # 3. Show existing ProductImage URLs
        try:
            from catalog.models import ProductImage
            images = ProductImage.objects.all().order_by("-pk")[:10]
            self.stdout.write(f"\nLast {images.count()} ProductImage records:")
            for img in images:
                try:
                    url = img.image.url
                    is_cloud = url.startswith("https://res.cloudinary.com")
                    marker = "✓ cloudinary" if is_cloud else "✗ local/broken"
                    self.stdout.write(f"  pk={img.pk} product={img.product_id}: {url} [{marker}]")
                except Exception as e:
                    self.stdout.write(f"  pk={img.pk}: ERROR getting url — {e}")
        except Exception as exc:
            self.stdout.write(f"Could not query ProductImage: {exc}")
