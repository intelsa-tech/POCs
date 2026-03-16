"""
Webflow CMS Structure Discovery — Intelsa

Corre esto UNA VEZ para descubrir el schema exacto de tu Collection de Servicios.
Guarda la salida — la necesitarás para configurar WEBFLOW_COLLECTION_ID en el .env

Uso:
    python webflow_discover.py
    python webflow_discover.py --slug servicio-atencion-cliente   # ver campos del template
    python webflow_discover.py --save                              # guarda resultado en webflow_schema.json
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
G = "\033[92m"   # verde
Y = "\033[93m"   # amarillo
C = "\033[96m"   # cyan
R = "\033[91m"   # rojo
B = "\033[1m"    # bold
E = "\033[0m"    # reset


def print_section(title: str):
    print(f"\n{B}{C}{'─'*60}{E}")
    print(f"{B}{C}  {title}{E}")
    print(f"{B}{C}{'─'*60}{E}")


def discover(template_slug: str | None = None, save: bool = False):
    print(f"\n{B}Webflow CMS Discovery — Intelsa{E}")

    # ── Sitio ─────────────────────────────────────────────────────────────────
    print_section("PASO 1 — Sitios")
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
    print_section("PASO 2 — Collections")
    coll_resp = list_collections(site_id)
    if "error" in coll_resp:
        print(f"  {R}✗ {coll_resp['error']}{E}")
        return

    collections = coll_resp.get("collections", [])
    schema_data = {}

    for coll in collections:
        name = coll.get("displayName") or coll.get("name", "?")
        slug = coll.get("slug", "")
        cid = coll["id"]
        print(f"  {G}•{E} {B}{name}{E}  slug: {Y}{slug}{E}  id: {C}{cid}{E}")
        schema_data[cid] = {"name": name, "slug": slug, "id": cid}

    if not collections:
        print(f"  {R}No se encontraron collections{E}")
        return

    # ── Schema de cada Collection ─────────────────────────────────────────────
    print_section("PASO 3 — Schema de campos por Collection")

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
            required = "* " if f.get("isRequired") else "  "
            print(f"    {required}{Y}{fslug:<30}{E} {fname:<30} [{ftype}]")
            field_list.append({"displayName": fname, "slug": fslug, "type": ftype, "required": f.get("isRequired", False)})

        schema_data[cid]["fields"] = field_list

        # Muestra 1 item de ejemplo
        items_resp = list_collection_items(cid, limit=2)
        items = items_resp.get("items", [])
        if items:
            print(f"\n    {C}Ejemplo de item existente:{E}")
            fd = items[0].get("fieldData", {})
            for k, v in list(fd.items())[:8]:
                val_preview = str(v)[:80] if v is not None else "null"
                print(f"      {Y}{k:<30}{E} = {val_preview}")
            if template_slug:
                schema_data[cid]["example_item"] = fd

    # ── Template item específico ──────────────────────────────────────────────
    if template_slug:
        print_section(f"PASO 4 — Campos del template: /{template_slug}")
        print(f"  Buscando slug '{template_slug}' en todas las collections…")

        template_data = None
        for coll in collections:
            cid = coll["id"]
            cname = coll.get("displayName") or coll.get("name", "?")
            items_resp = list_collection_items(cid, limit=100)
            items = items_resp.get("items", [])
            for item in items:
                fd = item.get("fieldData", {})
                item_slug = fd.get("slug", item.get("slug", ""))
                if item_slug == template_slug or item.get("id") == template_slug:
                    print(f"\n  {G}✓ Encontrado en Collection: {B}{cname}{E}  (id: {C}{cid}{E})")
                    print(f"  {G}  Item ID: {C}{item['id']}{E}\n")
                    print(f"  {B}Campos y valores del template:{E}")
                    for k, v in fd.items():
                        val_type = type(v).__name__
                        val_preview = json.dumps(v, ensure_ascii=False)[:120] if v is not None else "null"
                        print(f"    {Y}{k:<35}{E} [{val_type}] = {val_preview}")

                    template_data = {
                        "collection_id": cid,
                        "collection_name": cname,
                        "item_id": item["id"],
                        "field_data": fd,
                    }
                    schema_data["__template__"] = template_data
                    print(f"\n  {G}💡 Configura en .env:{E}")
                    print(f"     {B}WEBFLOW_COLLECTION_ID={cid}{E}")
                    print(f"     {B}WEBFLOW_TEMPLATE_ITEM_ID={item['id']}{E}")
                    break
            if template_data:
                break

        if not template_data:
            print(f"  {R}✗ No se encontró el slug '{template_slug}'. Verifica el slug exacto.{E}")

    # ── Guardar resultado ─────────────────────────────────────────────────────
    if save:
        out_path = Path(__file__).parent / "webflow_schema.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(schema_data, f, ensure_ascii=False, indent=2)
        print(f"\n  {G}✓ Schema guardado en: {B}{out_path}{E}")

    print(f"\n{'═'*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descubre la estructura CMS de Webflow — Intelsa")
    parser.add_argument("--slug", default="servicio-atencion-cliente",
                        help="Slug del item template (default: servicio-atencion-cliente)")
    parser.add_argument("--save", action="store_true",
                        help="Guarda el schema en webflow_schema.json")
    args = parser.parse_args()
    discover(template_slug=args.slug, save=args.save)
