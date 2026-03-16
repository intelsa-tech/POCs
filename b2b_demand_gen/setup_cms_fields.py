"""
Setup CMS Fields — Migración de páginas estáticas a CMS (Servicios)

Descubre la collection de Servicios, agrega los campos necesarios para almacenar
el copy generado por los agentes, y actualiza el .env con el collection_id.

Uso:
    python setup_cms_fields.py              # dry-run (solo muestra qué haría)
    python setup_cms_fields.py --apply      # aplica los cambios en Webflow
    python setup_cms_fields.py --apply --update-env  # aplica + actualiza .env

Campos que agrega a la Collection de Servicios:
    h1              PlainText   Título principal de la página
    hero-subtitle   PlainText   Subtítulo / propuesta de valor del hero
    meta-title      PlainText   SEO: título de la página
    meta-description PlainText  SEO: descripción
    cta-primary     PlainText   Texto del CTA principal
    content         RichText    Cuerpo del artículo (secciones como HTML)
    faq             RichText    Preguntas frecuentes como HTML
    cta-final       PlainText   CTA de cierre
"""

import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from tools.webflow_api import (
    list_sites,
    list_collections,
    get_collection,
    create_collection_field,
)

# ── Colores ANSI ──────────────────────────────────────────────────────────────
G = "\033[92m"
Y = "\033[93m"
C = "\033[96m"
R = "\033[91m"
B = "\033[1m"
E = "\033[0m"

# ── Campos que necesita el copy_data generado por los agentes ─────────────────
# Formato: (display_name, field_type, help_text)
REQUIRED_FIELDS = [
    ("H1",               "PlainText", "Título principal de la página"),
    ("Hero Subtitle",    "PlainText", "Subtítulo / propuesta de valor del hero"),
    ("Meta Title",       "PlainText", "SEO: meta title (60-70 chars)"),
    ("Meta Description", "PlainText", "SEO: meta description (máx 155 chars)"),
    ("CTA Primary",      "PlainText", "Texto del botón CTA principal"),
    ("Content",          "RichText",  "Cuerpo del artículo: secciones h2/h3/p como HTML"),
    ("FAQ",              "RichText",  "Preguntas frecuentes en formato HTML"),
    ("CTA Final",        "PlainText", "CTA de cierre al final de la página"),
]

# Nombre de la collection que buscamos (busca por display name, case-insensitive)
SERVICE_COLLECTION_KEYWORDS = ["servicio", "service"]


def _slug_from_name(display_name: str) -> str:
    """Genera el slug que Webflow usaría para un displayName."""
    slug = display_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def find_service_collection(collections: list) -> dict | None:
    """Busca la collection de Servicios por nombre."""
    for coll in collections:
        name = (coll.get("displayName") or coll.get("name", "")).lower()
        if any(k in name for k in SERVICE_COLLECTION_KEYWORDS):
            return coll
    return None


def get_existing_slugs(collection_id: str) -> set[str]:
    """Retorna el set de slugs de campos que ya existen en la collection."""
    schema = get_collection(collection_id)
    if "error" in schema:
        print(f"  {R}✗ Error al obtener schema: {schema['error']}{E}")
        return set()
    return {f.get("slug", "") for f in schema.get("fields", [])}


def run_setup(apply: bool = False, update_env: bool = False):
    print(f"\n{B}{'═'*60}{E}")
    print(f"{B}  Setup CMS Fields — Servicios Intelsa{E}")
    mode = f"{G}APPLY{E}" if apply else f"{Y}DRY-RUN{E}"
    print(f"{B}  Modo: {mode}{E}")
    print(f"{B}{'═'*60}{E}")

    # ── Sitio ─────────────────────────────────────────────────────────────────
    site_id = os.environ.get("WEBFLOW_SITE_ID", "")
    if not site_id:
        sites_resp = list_sites()
        if "error" in sites_resp:
            print(f"{R}✗ No se pudo conectar a Webflow: {sites_resp['error']}{E}")
            return
        sites = sites_resp.get("sites", [])
        if not sites:
            print(f"{R}✗ No se encontraron sitios{E}")
            return
        site_id = sites[0]["id"]
    print(f"\n  Site ID: {C}{site_id}{E}")

    # ── Collections ───────────────────────────────────────────────────────────
    coll_resp = list_collections(site_id)
    if "error" in coll_resp:
        print(f"{R}✗ Error al listar collections: {coll_resp['error']}{E}")
        return

    collections = coll_resp.get("collections", [])
    print(f"\n  Collections encontradas ({len(collections)}):")
    for c in collections:
        name = c.get("displayName") or c.get("name", "?")
        print(f"    {Y}•{E} {name:<30} id: {C}{c['id']}{E}")

    service_coll = find_service_collection(collections)
    if not service_coll:
        print(f"\n  {R}✗ No se encontró una collection de Servicios.{E}")
        print(f"  Busca collections con estas palabras clave: {SERVICE_COLLECTION_KEYWORDS}")
        print(f"  Collections disponibles: {[c.get('displayName') or c.get('name') for c in collections]}")
        return

    coll_id = service_coll["id"]
    coll_name = service_coll.get("displayName") or service_coll.get("name", "?")
    print(f"\n  {G}✓ Collection de Servicios:{E} {B}{coll_name}{E}  ({C}{coll_id}{E})")

    # ── Campos existentes ─────────────────────────────────────────────────────
    existing_slugs = get_existing_slugs(coll_id)
    print(f"\n  Campos ya existentes ({len(existing_slugs)}): {sorted(existing_slugs)}")

    # ── Plan: qué campos agregar ───────────────────────────────────────────────
    print(f"\n  {'─'*50}")
    print(f"  Plan de campos a agregar:")
    fields_to_add = []
    for display_name, field_type, help_text in REQUIRED_FIELDS:
        slug = _slug_from_name(display_name)
        if slug in existing_slugs:
            print(f"    {G}✓ EXISTE  {E} {Y}{slug:<25}{E} ({field_type})")
        else:
            print(f"    {C}+ AGREGAR {E} {Y}{slug:<25}{E} ({field_type})  — {display_name}")
            fields_to_add.append((display_name, field_type, help_text, slug))

    if not fields_to_add:
        print(f"\n  {G}✓ Todos los campos ya existen. No hay nada que agregar.{E}")
    elif not apply:
        print(f"\n  {Y}⚠  Modo dry-run: {len(fields_to_add)} campos pendientes.{E}")
        print(f"  Corre con --apply para crear los campos en Webflow.")
    else:
        print(f"\n  Creando {len(fields_to_add)} campos en Webflow...")
        created = 0
        for display_name, field_type, help_text, slug in fields_to_add:
            result = create_collection_field(
                collection_id=coll_id,
                field_type=field_type,
                display_name=display_name,
                is_required=False,
                help_text=help_text,
            )
            if "error" in result:
                print(f"    {R}✗ {display_name}: {result['error']}{E}")
            else:
                created_slug = result.get("slug", slug)
                print(f"    {G}✓ {display_name}{E}  → slug: {Y}{created_slug}{E}")
                created += 1
        print(f"\n  {G}✓ {created}/{len(fields_to_add)} campos creados.{E}")

    # ── Resumen .env ──────────────────────────────────────────────────────────
    print(f"\n  {'─'*50}")
    print(f"  {B}Agrega estas líneas a tu .env:{E}")
    print(f"  {G}WEBFLOW_COLLECTION_ID_SERVICE={coll_id}{E}")
    print(f"  {G}# WEBFLOW_TEMPLATE_ITEM_ID_SERVICE=  (dejar vacío hasta que el diseñador configure la Collection Template){E}")

    # ── Actualizar .env automáticamente ──────────────────────────────────────
    if update_env and apply:
        env_path = Path(__file__).parent / ".env"
        env_text = env_path.read_text()

        if f"WEBFLOW_COLLECTION_ID_SERVICE={coll_id}" in env_text:
            print(f"\n  {G}✓ .env ya tiene WEBFLOW_COLLECTION_ID_SERVICE correcto.{E}")
        else:
            env_text = re.sub(
                r"WEBFLOW_COLLECTION_ID_SERVICE=.*",
                f"WEBFLOW_COLLECTION_ID_SERVICE={coll_id}",
                env_text,
            )
            env_path.write_text(env_text)
            print(f"\n  {G}✓ .env actualizado con WEBFLOW_COLLECTION_ID_SERVICE={coll_id}{E}")

    print(f"\n{'═'*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Agrega campos CMS a la Collection de Servicios en Webflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios en Webflow (sin este flag es dry-run)",
    )
    parser.add_argument(
        "--update-env",
        action="store_true",
        help="Actualiza automáticamente el .env con el collection_id (requiere --apply)",
    )
    args = parser.parse_args()
    run_setup(apply=args.apply, update_env=args.update_env)
