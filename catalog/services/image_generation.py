"""
Wrapper around Gemini's image generation for backfilling product photos.

Two use cases:
  - generate_from_text(): product has 0 images — generate one from name/description.
  - generate_variation(): product has exactly 1 image — generate extra angles/
    variations using that image as reference, so the gallery has more than one photo.

Images are returned as raw bytes for the caller to save as a `ProductImage`
(never overwrites the original Dropi `images` JSON).

`ensure_product_image()` is the single entry point that both
`backfill_product_images` (bulk) and `import_products --generate-images`
(inline, per newly-imported product) call — keeps the "generate + save +
flag on failure" logic in one place.
"""
import logging
import mimetypes

import requests
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class ImageGenerationError(Exception):
    """Raised when Gemini fails to return a usable image."""


def _get_client():
    from google import genai

    if not settings.GEMINI_API_KEY:
        raise ImageGenerationError("GEMINI_API_KEY no está configurada.")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _extract_image_bytes(response) -> tuple[bytes, str]:
    """Pull the first inline image out of a Gemini generate_content response."""
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        parts = getattr(candidate.content, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and inline_data.data:
                return inline_data.data, inline_data.mime_type or "image/png"
    raise ImageGenerationError("Gemini no devolvió ninguna imagen en la respuesta.")


def generate_from_text(name: str, description: str = "") -> tuple[bytes, str]:
    """
    Generate a product photo from scratch using only the name/description.
    Used for products with 0 images. Returns (image_bytes, mime_type).
    """
    prompt = (
        "Genera una fotografía de producto de e-commerce, fondo blanco liso, "
        "iluminación de estudio, sin texto ni marcas de agua, estilo catálogo "
        f"profesional, del siguiente producto: {name}."
    )
    if description:
        prompt += f" Descripción: {description[:300]}"

    client = _get_client()
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_IMAGE_MODEL,
            contents=[prompt],
        )
    except Exception as exc:
        raise ImageGenerationError(str(exc)) from exc

    return _extract_image_bytes(response)


def generate_variation(reference_bytes: bytes, reference_mime_type: str, name: str) -> tuple[bytes, str]:
    """
    Generate an additional gallery photo using an existing product image as
    reference. Used for products with exactly 1 image, to give the gallery
    more than one angle/context shot. Returns (image_bytes, mime_type).
    """
    from google.genai import types

    prompt = (
        "Usa esta imagen de referencia de un producto de e-commerce y genera una "
        "variación fotográfica adicional del mismo producto (otro ángulo o un "
        "plano de contexto/estilo de vida), manteniendo el mismo producto, "
        f"fondo blanco o neutro, sin texto ni marcas de agua. Producto: {name}."
    )

    client = _get_client()
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_IMAGE_MODEL,
            contents=[
                prompt,
                types.Part.from_bytes(data=reference_bytes, mime_type=reference_mime_type),
            ],
        )
    except Exception as exc:
        raise ImageGenerationError(str(exc)) from exc

    return _extract_image_bytes(response)


def _ext_for_mime(mime_type: str) -> str:
    return mimetypes.guess_extension(mime_type) or ".png"


def ensure_product_image(product) -> str:
    """
    Make sure `product` has at least 2 images, generating with Gemini if needed.
    Saves results as `ProductImage` rows — never touches Dropi's `images` JSON.

    Returns one of:
      "skipped"   — already has custom images or >=2 Dropi images, nothing done.
      "generated" — new ProductImage created.
      "flagged"   — 0-image product, generation failed, marked image_flagged=True.
      "error"     — 1-image product, generation failed, not flagged (still sellable
                    with its single existing photo).
    """
    from catalog.models import ProductImage  # local import: avoid app-loading cycle

    if product.custom_images.exists():
        return "skipped"

    image_count = len(product.images or [])
    if image_count >= 2:
        return "skipped"

    kind = "zero" if image_count == 0 else "one"

    try:
        if kind == "zero":
            image_bytes, mime_type = generate_from_text(product.name, product.description)
        else:
            ref_url = product.main_image
            if not ref_url:
                raise ImageGenerationError("Sin main_image para usar como referencia.")
            ref_resp = requests.get(ref_url, timeout=REQUEST_TIMEOUT)
            ref_resp.raise_for_status()
            ref_mime = ref_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
            image_bytes, mime_type = generate_variation(ref_resp.content, ref_mime, product.name)
    except (ImageGenerationError, requests.RequestException) as exc:
        logger.warning("Image generation failed for product %s: %s", product.pk, exc)
        if kind == "zero":
            product.image_flagged = True
            product.save(update_fields=["image_flagged"])
            return "flagged"
        return "error"

    filename = f"gemini_{product.pk}_{kind}{_ext_for_mime(mime_type)}"
    ProductImage.objects.create(
        product=product,
        image=ContentFile(image_bytes, name=filename),
        order=0 if kind == "zero" else 1,
    )
    return "generated"
