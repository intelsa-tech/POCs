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
    list_pages,
    get_page_dom,
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
        all_items = items_resp.get("items", [])
        print(f"    → {len(all_items)} items en '{cname}': {[i.get('fieldData', {}).get('slug', i.get('slug', i['id'])) for i in all_items]}")
        for item in all_items:
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


def find_static_page(pages: list, folder_slug: str, page_slug: str) -> dict | None:
    """
    Busca una página estática por slug.
    En Webflow las carpetas no aparecen como páginas — solo se ven como parentId en las páginas hijas.
    Se busca primero por slug exacto; si hay duplicados, se usa folder_slug para filtrar por hermanos.
    """
    print(f"\n  Buscando página estática: '{folder_slug}/{page_slug}'…")

    # Buscar todas las páginas con ese slug
    matches = [p for p in pages if p.get("slug") == page_slug]

    if not matches:
        print(f"  {R}✗ No se encontró ninguna página con slug '{page_slug}'. Páginas disponibles:{E}")
        for p in pages:
            slug = p.get("slug") or "—"
            print(f"    • {Y}{slug:<40}{E} {p.get('title', '?')}  (parentId: {p.get('parentId', 'root')})")
        return None

    # Si hay más de una, intentar filtrar por el parentId compartido con hermanos del folder
    page = matches[0]
    if len(matches) > 1:
        # Inferir folder_id desde otro hermano con el mismo parentId
        siblings = [p for p in pages if p.get("slug") in (folder_slug,) or
                    any(m.get("parentId") == p.get("parentId") for m in matches if p.get("parentId"))]
        print(f"  {Y}⚠  {len(matches)} páginas con ese slug, usando la primera.{E}")

    page_id = page["id"]
    folder_id = page.get("parentId")
    print(f"  {G}✓ Página encontrada:{E} '{page.get('title')}' (id: {C}{page_id}{E})")
    print(f"     parentId (carpeta): {C}{folder_id}{E}")

    # Obtener el DOM de la página
    print(f"\n  Obteniendo DOM de la página…")
    dom = get_page_dom(page_id)
    if "error" in dom:
        print(f"  {R}✗ Error al obtener DOM: {dom['error']}{E}")
        dom = {}
    else:
        nodes = dom.get("nodes", [])
        print(f"  {G}✓ DOM obtenido:{E} {len(nodes)} nodos")

    return {
        "page_id": page_id,
        "folder_id": folder_id,
        "folder_slug": folder_slug,
        "page_slug": page_slug,
        "title": page.get("title", ""),
        "dom": dom,
    }


def discover(
    service_slug: str | None = None,
    industry_slug: str | None = None,
    blog_slug: str | None = None,
    page_path: str | None = None,
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

    # ── Páginas estáticas ─────────────────────────────────────────────────────
    static_page_result = None
    if page_path:
        print_section("PASO 4b — Página estática (folder/page)")
        pages_resp = list_pages(site_id)
        if "error" in pages_resp:
            print(f"  {R}✗ {pages_resp['error']}{E}")
        else:
            all_pages = pages_resp.get("pages", [])
            print(f"  {G}✓{E} {len(all_pages)} páginas encontradas en el sitio")
            parts = page_path.strip("/").split("/", 1)
            if len(parts) == 2:
                static_page_result = find_static_page(all_pages, parts[0], parts[1])
                if static_page_result:
                    env_lines.append(f"WEBFLOW_STATIC_PAGE_ID={static_page_result['page_id']}")
                    env_lines.append(f"WEBFLOW_STATIC_FOLDER_ID={static_page_result['folder_id']}")
            else:
                print(f"  {R}✗ Formato inválido. Usa: carpeta/pagina  (ej: servicios/servicio-atencion-cliente){E}")

    # ── Resumen .env ──────────────────────────────────────────────────────────
    if env_lines:
        print_section("RESULTADO — Agrega estas líneas a tu .env")
        for line in env_lines:
            print(f"  {G}{B}{line}{E}")

    # ── Guardar ───────────────────────────────────────────────────────────────
    output = {"collections": schema_data, "templates": templates}
    if static_page_result:
        output["static_page"] = {k: v for k, v in static_page_result.items() if k != "dom"}
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
    parser.add_argument("--service",  metavar="SLUG", help="Slug del item template para Servicios (CMS)")
    parser.add_argument("--industry", metavar="SLUG", help="Slug del item template para Industrias (CMS)")
    parser.add_argument("--blog",     metavar="SLUG", help="Slug del item template para Blog (CMS)")
    parser.add_argument("--page",     metavar="FOLDER/PAGE", help="Ruta de página estática, ej: servicios/servicio-atencion-cliente")
    parser.add_argument("--save", action="store_true", help="Guarda el schema en webflow_schema.json")
    args = parser.parse_args()

    # Si no se pasan slugs de CMS, omitir búsqueda CMS
    service_slug = args.service if args.service else None
    if not any([args.service, args.industry, args.blog, args.page]):
        service_slug = "servicio-atencion-cliente"  # default legacy

    discover(
        service_slug=service_slug,
        industry_slug=args.industry,
        blog_slug=args.blog,
        page_path=args.page,
        save=args.save,
    )
