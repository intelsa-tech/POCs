"""
Webflow CMS Structure Discovery — Intelsa

Descubre el schema exacto de tus Collections y obtiene los IDs de los items template
para configurar el .env correctamente.

Uso:
    python webflow_discover.py                        # descubre todo, usa slugs por defecto
    python webflow_discover.py --service slug-here    # slug del template de servicios
    python webflow_discover.py --industry slug-here   # slug del template de industrias
    python webflow_discover.py --blog slug-here       # slug del template de blog
    python webflow_discover.py --save                 # guarda resultado en webflow_schema.json

Ejemplo completo:
    python webflow_discover.py \\
        --service servicio-atencion-cliente \\
        --industry industria-retail \\
        --blog primer-articulo \\
        --save
"""

import json
import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from tools.webflow_api import (
    list_sites,
    list_collections,
    get_collection,
    list_collection_items,
    get_item,
)

# ── Colores ANSI ──────────────────────────────────────────────────────────────
G = "\033[92m"
Y = "\033[93m"
C = "\033[96m"
R = "\033[91m"
B = "\033[1m"
E = "\033[0m"


def print_section(title: str):
    print(f"\n{B}{C}{'─'*60}{E}")
    print(f"{B}{C}  {title}{E}")
    print(f"{B}{C}{'─'*60}{E}")


def find_template_item(collections: list, slug: str, label: str) -> dict | None:
    """Busca un item por slug en todas las collections y retorna su info."""
    print(f"\n  Buscando template de {label}: slug='{slug}'…")
    for coll in collections:
        cid = coll["id"]
        cname = coll.get("displayName") or coll.get("name", "?")
        items_resp = list_collection_items(cid, limit=100)
        if "error" in items_resp:
            continue
        for item in items_resp.get("items", []):
            fd = item.get("fieldData", {})
            item_slug = fd.get("slug", item.get("slug", ""))
            if item_slug == slug or item.get("id") == slug:
                print(f"  {G}✓ Encontrado en: {B}{cname}{E}  (collection_id: {C}{cid}{E})")
                print(f"  {G}  Item ID: {C}{item['id']}{E}\n")

                # Obtener el item completo para ver todos sus campos
                full_item = get_item(cid, item["id"])
                fd_full = full_item.get("fieldData", fd)

                print(f"  {B}Campos del template ({len(fd_full)} campos):{E}")
                for k, v in fd_full.items():
                    val_type = type(v).__name__
                    val_preview = json.dumps(v, ensure_ascii=False)[:100] if v is not None else "null"
                    print(f"    {Y}{k:<35}{E} [{val_type:<8}] {val_preview}")

                return {
                    "collection_id": cid,
                    "collection_name": cname,
                    "item_id": item["id"],
                    "field_data": fd_full,
                }

    print(f"  {R}✗ No se encontró el slug '{slug}'. Verifica el slug exacto en la URL de Webflow.{E}")
    return None


def discover(
    service_slug: str | None = None,
    industry_slug: str | None = None,
    blog_slug: str | None = None,
    save: bool = False,
):
    print(f"\n{B}{'═'*60}{E}")
    print(f"{B}  Webflow CMS Discovery — Intelsa{E}")
    print(f"{B}{'═'*60}{E}")

    # ── Sitio ─────────────────────────────────────────────────────────────────
    print_section("PASO 1 — Sitios disponibles")
    sites_resp = list_sites()
    if "error" in sites_resp:
        print(f"  {R}✗ {sites_resp['error']}{E}")
        return

    sites = sites_resp.get("sites", [])
    for s in sites:
        print(f"  {G}✓{E} {B}{s['displayName']}{E}  id: {C}{s['id']}{E}")

    if not sites:
        print(f"  {R}No se encontraron sitios{E}")
        return

    site_id = os.environ.get("WEBFLOW_SITE_ID") or sites[0]["id"]
    print(f"\n  → Usando site_id: {C}{site_id}{E}")

    # ── Collections ───────────────────────────────────────────────────────────
    print_section("PASO 2 — Collections del sitio")
    coll_resp = list_collections(site_id)
    if "error" in coll_resp:
        print(f"  {R}✗ {coll_resp['error']}{E}")
        return

    collections = coll_resp.get("collections", [])
    for coll in collections:
        name = coll.get("displayName") or coll.get("name", "?")
        slug = coll.get("slug", "")
        cid = coll["id"]
        print(f"  {G}•{E} {B}{name:<30}{E} slug: {Y}{slug:<25}{E} id: {C}{cid}{E}")

    if not collections:
        print(f"  {R}No se encontraron collections{E}")
        return

    # ── Templates por tipo ────────────────────────────────────────────────────
    print_section("PASO 3 — Templates por tipo de página")
    templates = {}
    env_lines = []

    slugs_to_find = []
    if service_slug:
        slugs_to_find.append(("service", service_slug, "Servicios"))
    if industry_slug:
        slugs_to_find.append(("industry", industry_slug, "Industrias"))
    if blog_slug:
        slugs_to_find.append(("blog", blog_slug, "Blog"))

    if not slugs_to_find:
        print(f"  {Y}⚠  No se especificaron slugs de template. Usa --service, --industry o --blog.{E}")
        print(f"  Ejemplo: python webflow_discover.py --service servicio-atencion-cliente")
    else:
        for page_type, slug, label in slugs_to_find:
            result = find_template_item(collections, slug, label)
            if result:
                templates[page_type] = result
                env_lines.append(f"WEBFLOW_COLLECTION_ID_{page_type.upper()}={result['collection_id']}")
                env_lines.append(f"WEBFLOW_TEMPLATE_ITEM_ID_{page_type.upper()}={result['item_id']}")

    # ── Schema de todas las collections ───────────────────────────────────────
    print_section("PASO 4 — Campos por Collection")
    schema_data = {}

    for coll in collections:
        name = coll.get("displayName") or coll.get("name", "?")
        cid = coll["id"]
        print(f"\n  {B}Collection: {name}{E}  ({C}{cid}{E})")

        schema = get_collection(cid)
        if "error" in schema:
            print(f"    {R}✗ {schema['error']}{E}")
            continue

        fields = schema.get("fields", [])
        field_list = []
        for f in fields:
            fname = f.get("displayName") or f.get("name", "?")
            fslug = f.get("slug", "")
            ftype = f.get("type", "?")
            required = f"{R}*{E} " if f.get("isRequired") else "  "
            print(f"    {required}{Y}{fslug:<30}{E} {fname:<28} [{ftype}]")
            field_list.append({
                "displayName": fname,
                "slug": fslug,
                "type": ftype,
                "required": f.get("isRequired", False),
            })

        schema_data[cid] = {
            "name": name,
            "slug": coll.get("slug", ""),
            "id": cid,
            "fields": field_list,
        }

    # ── Resumen .env ──────────────────────────────────────────────────────────
    if env_lines:
        print_section("RESULTADO — Agrega estas líneas a tu .env")
        for line in env_lines:
            print(f"  {G}{B}{line}{E}")

    # ── Guardar ───────────────────────────────────────────────────────────────
    output = {"collections": schema_data, "templates": templates}
    if save:
        out_path = Path(__file__).parent / "webflow_schema.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n  {G}✓ Schema completo guardado en: {B}{out_path}{E}")

    print(f"\n{'═'*60}\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Descubre la estructura CMS de Webflow — Intelsa",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--service",  metavar="SLUG", help="Slug del item template para Servicios")
    parser.add_argument("--industry", metavar="SLUG", help="Slug del item template para Industrias")
    parser.add_argument("--blog",     metavar="SLUG", help="Slug del item template para Blog")
    parser.add_argument("--save", action="store_true", help="Guarda el schema en webflow_schema.json")
    args = parser.parse_args()

    # Si no se pasan slugs, usa el de servicios por defecto
    service_slug = args.service or ("servicio-atencion-cliente" if not any([args.industry, args.blog]) else None)

    discover(
        service_slug=service_slug,
        industry_slug=args.industry,
        blog_slug=args.blog,
        save=args.save,
    )
