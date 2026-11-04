# Arquitectura de tienda — Pegasus Store

## Fase actual: catálogo

La home (`/`) muestra solo secciones de catálogo configuradas en `CATALOG_HOME_SECTIONS`:

| ID | Template | Estado |
|----|----------|--------|
| `catalog_header` | `catalog/partials/section_catalog_header.html` | Activo |
| `catalog_grid` | `catalog/partials/section_catalog_grid.html` | Activo |
| `featured` | — | Planificado |
| `offers` | — | Planificado |
| `novedades` | — | Planificado |

## Cómo añadir una sección futura

1. Implementar builder en [`catalog/sections.py`](../../catalog/sections.py) y registrar en `_SECTION_BUILDERS`.
2. Crear partial `templates/catalog/partials/section_<id>.html`.
3. Activar en [`config/settings.py`](../../config/settings.py): `{"id": "<id>", "enabled": True}`.

La vista [`catalog_index`](../../catalog/views.py) no debe crecer: solo pasa `shared` a `build_home_sections()`.

## Categorías

- Filtro actual: `?category=<dropi_id>` (compatible con Dropi).
- UI: chips (móvil) + sidebar (desktop) en `section_catalog_grid.html`.
- Fase 2: `Category.slug` y ruta `/categoria/<slug>/`.

## Tarjeta de producto

Reutilizar [`catalog/partials/product_card.html`](../../templates/catalog/partials/product_card.html) en ofertas/novedades cuando existan.
