"""
Webflow REST API v2 wrapper.
Todos los métodos retornan dicts listos para ser usados como tool_result de Claude.
"""

import os
import httpx
from typing import Any

WEBFLOW_BASE_URL = "https://api.webflow.com/v2"


def _get_headers() -> dict:
    token = os.environ.get("WEBFLOW_API_TOKEN")
    if not token:
        raise ValueError("WEBFLOW_API_TOKEN no está definido en las variables de entorno")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _handle_response(response: httpx.Response) -> dict:
    """Maneja la respuesta de Webflow con errores descriptivos."""
    if response.status_code == 401:
        return {"error": "401 Unauthorized - El WEBFLOW_API_TOKEN es inválido o expiró. Genera uno nuevo en Webflow > Site Settings > Apps & Integrations > API Access."}
    if response.status_code == 403:
        return {"error": "403 Forbidden - El token no tiene permisos suficientes. Necesita scopes: sites:read, cms:read, cms:write. Regenera el token con estos permisos."}
    if response.status_code == 404:
        return {"error": f"404 Not Found - El recurso no existe. Verifica los IDs de site/collection."}
    if response.status_code >= 400:
        detail = response.text[:300] if response.text else "Sin detalle"
        return {"error": f"Error {response.status_code}: {detail}"}
    return response.json()


def list_sites() -> dict:
    """Lista todos los sitios Webflow asociados al token."""
    with httpx.Client() as client:
        response = client.get(f"{WEBFLOW_BASE_URL}/sites", headers=_get_headers())
        return _handle_response(response)


def list_collections(site_id: str) -> dict:
    """Lista todas las Collections de un sitio."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/sites/{site_id}/collections",
            headers=_get_headers(),
        )
        return _handle_response(response)


def get_collection(collection_id: str) -> dict:
    """Obtiene el schema de una Collection (campos disponibles)."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}",
            headers=_get_headers(),
        )
        return _handle_response(response)


def list_collection_items(collection_id: str, limit: int = 10) -> dict:
    """Lista items existentes en una Collection (útil para ver el formato esperado)."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}/items",
            headers=_get_headers(),
            params={"limit": limit},
        )
        return _handle_response(response)


def get_item(collection_id: str, item_id: str) -> dict:
    """Obtiene un item específico de una Collection (útil para usar como template)."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}/items/{item_id}",
            headers=_get_headers(),
        )
        return _handle_response(response)


def create_collection_item(collection_id: str, field_data: dict[str, Any]) -> dict:
    """
    Crea un nuevo item (página) en una Collection de Webflow.

    Args:
        collection_id: ID de la Collection destino.
        field_data: Diccionario con los campos del item.
                    Debe incluir al menos 'name' y 'slug'.
    """
    payload = {
        "isArchived": False,
        "isDraft": True,
        "fieldData": field_data,
    }
    with httpx.Client() as client:
        response = client.post(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}/items",
            headers=_get_headers(),
            json=payload,
        )
        return _handle_response(response)


def list_pages(site_id: str) -> dict:
    """Lista todas las páginas estáticas de un sitio (incluyendo las de carpetas)."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/sites/{site_id}/pages",
            headers=_get_headers(),
        )
        return _handle_response(response)


def get_page_dom(page_id: str) -> dict:
    """Obtiene el DOM/estructura de una página estática de Webflow."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/pages/{page_id}/dom",
            headers=_get_headers(),
        )
        return _handle_response(response)


def publish_item(collection_id: str, item_id: str) -> dict:
    """Publica un item draft en Webflow (lo hace visible en el sitio)."""
    with httpx.Client() as client:
        response = client.post(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}/items/publish",
            headers=_get_headers(),
            json={"itemIds": [item_id]},
        )
        return _handle_response(response)
