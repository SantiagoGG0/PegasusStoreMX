"""Normalización de paths y detección de bypass hacia el admin Django."""

from __future__ import annotations

import re
from urllib.parse import unquote

_LEGACY_ADMIN_PREFIX = "/admin"


def normalize_request_path(path: str) -> str:
    """Colapsa trucos comunes de path (//, /./, ;matrix, %20, segmentos con '.')."""
    if not path:
        return "/"

    if "?" in path:
        path = path.split("?", 1)[0]
    if "#" in path:
        path = path.split("#", 1)[0]

    path = unquote(path)
    path = path.split(";", 1)[0]

    while "//" in path:
        path = path.replace("//", "/")

    trailing_slash = path.endswith("/")
    stack: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if stack:
                stack.pop()
            continue
        cleaned = segment.strip().rstrip(".")
        if cleaned:
            stack.append(cleaned)

    if not stack:
        return "/" if trailing_slash else "/"

    result = "/" + "/".join(stack)
    if trailing_slash and not result.endswith("/"):
        result += "/"
    return result


def has_admin_path_bypass_markers(raw_path: str) -> bool:
    """True si el path crudo usa técnicas típicas de evasión de WAF."""
    decoded = unquote(raw_path)

    if ";" in decoded:
        return True
    if "//" in decoded:
        return True
    if re.search(r"/\.(?:/|$)", decoded):
        return True
    if "/./" in decoded or decoded.startswith("./"):
        return True
    if re.search(r"/\.\./", decoded):
        return True
    if "%" in raw_path:
        return True

    return False


def _normalized_lower(path: str) -> str:
    return normalize_request_path(path).lower()


def targets_admin_path(path: str, admin_slug: str) -> bool:
    """True si el path normalizado apunta al admin legado o al slug configurado."""
    normalized = _normalized_lower(path)
    slug = admin_slug.strip("/").lower()
    custom_prefix = f"/{slug}"

    if normalized == _LEGACY_ADMIN_PREFIX or normalized.startswith(
        f"{_LEGACY_ADMIN_PREFIX}/"
    ):
        return True

    return normalized == custom_prefix or normalized.startswith(f"{custom_prefix}/")


def should_block_admin_path(raw_path: str, admin_slug: str) -> bool:
    """
    Bloquea /admin (y variantes) siempre.
    Bloquea el admin real si el path usa trucos de normalización.
    """
    if not targets_admin_path(raw_path, admin_slug):
        return False

    normalized = _normalized_lower(raw_path)
    if normalized == _LEGACY_ADMIN_PREFIX or normalized.startswith(
        f"{_LEGACY_ADMIN_PREFIX}/"
    ):
        return True

    return has_admin_path_bypass_markers(raw_path)
