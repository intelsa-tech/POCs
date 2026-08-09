#!/usr/bin/env python3
"""
Diagnóstico de conexión Webflow para Intelsa B2B Content Generator.

Prueba la conexión en 4 pasos:
  1. Autenticación — verifica que el token sea válido
  2. Sitio — confirma acceso al WEBFLOW_SITE_ID configurado
  3. Collections — lista todas las collections disponibles
  4. Test Item — (opcional) crea un item de prueba en una collection

Uso:
    cd b2b_demand_gen
    python webflow_test.py             # solo diagnóstico (no crea nada)
    python webflow_test.py --create    # diagnóstico + crea item de prueba
    python webflow_test.py --delete ID # elimina el item de prueba creado
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://api.webflow.com/v2"
TOKEN    = os.environ.get("WEBFLOW_API_TOKEN", "")
SITE_ID  = os.environ.get("WEBFLOW_SITE_ID", "")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def err(msg): print(f"  {RED}✗{RESET} {msg}")
def warn(msg):print(f"  {YELLOW}⚠{RESET} {msg}")
def info(msg):print(f"  {CYAN}→{RESET} {msg}")
def head(msg):print(f"\n{BOLD}{msg}{RESET}")


def headers() -> dict:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _get(url: str) -> httpx.Response | None:
    """GET con manejo de ProxyError del entorno de desarrollo."""
    try:
        return httpx.get(url, headers=headers(), timeout=10)
    except httpx.ProxyError:
        _proxy_error()
        return None
    except httpx.ConnectError as e:
        err(f"Error de conexión: {e}")
        return None

def _post(url: str, payload: dict) -> httpx.Response | None:
    try:
        return httpx.post(url, headers=headers(), json=payload, timeout=10)
    except httpx.ProxyError:
        _proxy_error()
        return None

def _delete(url: str) -> httpx.Response | None:
    try:
        return httpx.delete(url, headers=headers(), timeout=10)
    except httpx.ProxyError:
        _proxy_error()
        return None

def _proxy_error():
    print()
    err("ProxyError 403 — El entorno de servidor bloquea conexiones salientes directas.")
    err("Este script debe ejecutarse en tu MÁQUINA LOCAL, no en el servidor.")
    print(f"\n  {YELLOW}Pasos para ejecutarlo local:{RESET}")
    print(f"    1. git pull origin claude/b2b-demand-generation-page-zBQJI")
    print(f"    2. cd b2b_demand_gen")
    print(f"    3. pip install httpx python-dotenv")
    print(f"    4. python webflow_test.py")
    print(f"    5. python webflow_test.py --create   (para el Hola Mundo)")
    sys.exit(1)

def step1_auth() -> bool:
    """Paso 1: Verifica autenticación listando sitios."""
    head("PASO 1 — Autenticación (GET /sites)")
    if not TOKEN:
        err("WEBFLOW_API_TOKEN no está definido en el .env")
        return False
    info(f"Token: {TOKEN[:12]}...{TOKEN[-6:]}")

    resp = _get(f"{BASE_URL}/sites")
    if resp is None: return False
    if resp.status_code == 200:
        sites = resp.json().get("sites", [])
        ok(f"Token válido — {len(sites)} sitio(s) accesible(s):")
        for s in sites:
            info(f"  {s.get('displayName', '?')}  (id: {s.get('id', '?')})")
        return True
    elif resp.status_code == 401:
        err("401 Unauthorized — El token es inválido o expiró")
        err("Solución: Webflow > Site Settings > Apps & Integrations > API Access → generar nuevo token")
        return False
    elif resp.status_code == 403:
        err("403 Forbidden — El token no tiene permiso para listar sitios")
        err("Solución: El token necesita scope 'sites:read' al menos")
        return False
    else:
        err(f"Error inesperado {resp.status_code}: {resp.text[:200]}")
        return False


def step2_site() -> bool:
    """Paso 2: Accede al sitio configurado."""
    head("PASO 2 — Acceso al sitio (GET /sites/{id})")
    if not SITE_ID:
        warn("WEBFLOW_SITE_ID no está definido en el .env")
        warn("Define el Site ID para que el agente no tenga que auto-descubrirlo cada vez")
        return False
    info(f"Site ID: {SITE_ID}")

    resp = _get(f"{BASE_URL}/sites/{SITE_ID}")
    if resp is None: return False
    if resp.status_code == 200:
        site = resp.json()
        ok(f"Sitio encontrado: {site.get('displayName', '?')}")
        ok(f"  Short name: {site.get('shortName', '?')}.webflow.io")
        ok(f"  Publicado: {site.get('lastPublished', 'nunca')}")
        return True
    elif resp.status_code == 404:
        err(f"Sitio {SITE_ID} no encontrado")
        err("Verifica que el WEBFLOW_SITE_ID en el .env sea correcto")
        return False
    else:
        err(f"Error {resp.status_code}: {resp.text[:200]}")
        return False


def step3_collections() -> list[dict]:
    """Paso 3: Lista las collections del sitio."""
    head("PASO 3 — Collections del sitio (GET /sites/{id}/collections)")
    if not SITE_ID:
        warn("Saltando — WEBFLOW_SITE_ID no configurado")
        return []

    resp = _get(f"{BASE_URL}/sites/{SITE_ID}/collections")
    if resp is None: return []
    if resp.status_code == 200:
        cols = resp.json().get("collections", [])
        ok(f"{len(cols)} collection(s) encontrada(s):")
        for c in cols:
            info(f"  [{c.get('id','?')}]  {c.get('displayName','?')}  (slug: /{c.get('slug','?')})")
        return cols
    elif resp.status_code == 403:
        err("403 — El token no tiene scope 'cms:read'")
        err("Regenera el token con scopes: sites:read, cms:read, cms:write")
        return []
    else:
        err(f"Error {resp.status_code}: {resp.text[:200]}")
        return []


def step4_schema(collection: dict):
    """Muestra el schema de una collection (campos disponibles)."""
    cid = collection["id"]
    name = collection.get("displayName", "?")
    head(f"PASO 4 — Schema de '{name}' (GET /collections/{cid})")

    resp = _get(f"{BASE_URL}/collections/{cid}")
    if resp is None: return
    if resp.status_code != 200:
        err(f"Error {resp.status_code}: {resp.text[:200]}")
        return

    fields = resp.json().get("fields", [])
    ok(f"{len(fields)} campo(s) en esta collection:")
    required = []
    for f in fields:
        label   = f.get("displayName", f.get("slug", "?"))
        ftype   = f.get("type", "?")
        req     = f.get("isRequired", False)
        marker  = f" {RED}[required]{RESET}" if req else ""
        info(f"  {label}  ({ftype}){marker}")
        if req:
            required.append(f.get("slug", label))

    if required:
        print()
        warn(f"Campos requeridos al crear un item: {', '.join(required)}")


def step5_create_test(collection: dict) -> str | None:
    """Crea un item de prueba 'Hola mundo' en la collection."""
    cid  = collection["id"]
    name = collection.get("displayName", "?")
    head(f"PASO 5 — Crear item de prueba en '{name}'")

    payload = {
        "isArchived": False,
        "isDraft": True,
        "fieldData": {
            "name": "🧪 Test Intelsa — Hola Mundo",
            "slug": "test-intelsa-hola-mundo",
        },
    }
    info(f"POST /collections/{cid}/items  (isDraft=true, no será visible en el sitio)")
    info(f"Payload: {json.dumps(payload['fieldData'], ensure_ascii=False)}")

    resp = _post(f"{BASE_URL}/collections/{cid}/items", payload)
    if resp is None: return None

    if resp.status_code in (200, 201):
        item = resp.json()
        item_id = item.get("id", "")
        ok(f"¡Item creado exitosamente!")
        ok(f"  ID:   {item_id}")
        ok(f"  Name: {item.get('fieldData', {}).get('name', '?')}")
        ok(f"  Slug: {item.get('fieldData', {}).get('slug', '?')}")
        warn(f"El item está como DRAFT — no es visible en el sitio publicado")
        warn(f"Para eliminarlo: python webflow_test.py --delete {cid}/{item_id}")
        return f"{cid}/{item_id}"
    elif resp.status_code == 400:
        err(f"400 Bad Request — la collection probablemente tiene campos requeridos adicionales")
        err(f"Detalle: {resp.text[:400]}")
        err(f"Solución: revisa los campos requeridos en el PASO 4 y ajusta el payload")
    elif resp.status_code == 403:
        err("403 — El token no tiene scope 'cms:write'")
        err("Regenera el token con scopes: sites:read, cms:read, cms:write")
    else:
        err(f"Error {resp.status_code}: {resp.text[:400]}")
    return None


def step_delete(collection_id: str, item_id: str):
    """Elimina el item de prueba."""
    head(f"ELIMINAR item de prueba")
    info(f"DELETE /collections/{collection_id}/items/{item_id}")

    resp = _delete(f"{BASE_URL}/collections/{collection_id}/items/{item_id}")
    if resp is None: return
    if resp.status_code in (200, 202, 204):
        ok("Item eliminado correctamente")
    else:
        err(f"Error {resp.status_code}: {resp.text[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico de conexión Webflow")
    parser.add_argument("--create", action="store_true", help="Crear item de prueba 'Hola Mundo'")
    parser.add_argument("--delete", metavar="COLLECTION_ID/ITEM_ID",
                        help="Eliminar item de prueba (formato: collection_id/item_id)")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Webflow Connection Diagnostics — Intelsa{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # Modo eliminación
    if args.delete:
        parts = args.delete.split("/")
        if len(parts) != 2:
            err("Formato incorrecto. Usa: --delete COLLECTION_ID/ITEM_ID")
            sys.exit(1)
        step_delete(parts[0], parts[1])
        sys.exit(0)

    # Paso 1: Auth
    if not step1_auth():
        print(f"\n{RED}❌ Autenticación fallida — corrige el token y vuelve a intentar{RESET}\n")
        sys.exit(1)

    # Paso 2: Site
    site_ok = step2_site()

    # Paso 3: Collections
    collections = step3_collections() if site_ok else []

    # Paso 4 + 5: Schema y creación de test
    if collections:
        # Mostrar schema de la primera collection
        step4_schema(collections[0])

        if args.create:
            result = step5_create_test(collections[0])
            if result:
                print(f"\n{GREEN}{BOLD}✅ ¡Conexión completamente funcional!{RESET}")
                print(f"   Puedes ver el item draft en: Webflow CMS > {collections[0].get('displayName','?')}")
                print(f"   Para eliminarlo: python webflow_test.py --delete {result}\n")
        else:
            print(f"\n{CYAN}Tip: usa --create para crear un item de prueba y confirmar escritura completa{RESET}\n")
    elif site_ok:
        warn("No hay collections en este sitio — crea una en Webflow Designer primero")

    # Resumen
    print(f"\n{BOLD}{'='*60}{RESET}")
    if not site_ok:
        print(f"{YELLOW}⚠  Configura WEBFLOW_SITE_ID en el .env con el ID de tu sitio{RESET}")
    elif not collections:
        print(f"{YELLOW}⚠  Crea al menos una Collection en Webflow para usar el pipeline{RESET}")
    else:
        print(f"{GREEN}✓  Conexión básica OK — token válido, sitio accesible, {len(collections)} collection(s){RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")


if __name__ == "__main__":
    main()
