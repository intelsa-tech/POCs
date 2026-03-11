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


def list_sites() -> dict:
    """Lista todos los sitios Webflow asociados al token."""
    with httpx.Client() as client:
        response = client.get(f"{WEBFLOW_BASE_URL}/sites", headers=_get_headers())
        response.raise_for_status()
        return response.json()


def list_collections(site_id: str) -> dict:
    """Lista todas las Collections de un sitio."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/sites/{site_id}/collections",
            headers=_get_headers(),
        )
        response.raise_for_status()
        return response.json()


def get_collection(collection_id: str) -> dict:
    """Obtiene el schema de una Collection (campos disponibles)."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}",
            headers=_get_headers(),
        )
        response.raise_for_status()
        return response.json()


def list_collection_items(collection_id: str, limit: int = 10) -> dict:
    """Lista items existentes en una Collection (útil para ver el formato esperado)."""
    with httpx.Client() as client:
        response = client.get(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}/items",
            headers=_get_headers(),
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json()


def create_collection_item(collection_id: str, field_data: dict[str, Any]) -> dict:
    """
    Crea un nuevo item (página) en una Collection de Webflow.

    Args:
        collection_id: ID de la Collection destino.
        field_data: Diccionario con los campos del item.
                    Debe incluir al menos 'name' y 'slug'.
                    Ejemplo: {
                        "name": "Generación de Demanda B2B",
                        "slug": "generacion-demanda-b2b",
                        "hero-title": "...",
                        "body-copy": "...",
                        ...
                    }
    """
    payload = {
        "isArchived": False,
        "isDraft": True,  # Empieza como draft para revisión
        "fieldData": field_data,
    }
    with httpx.Client() as client:
        response = client.post(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}/items",
            headers=_get_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def publish_item(collection_id: str, item_id: str) -> dict:
    """Publica un item draft en Webflow (lo hace visible en el sitio)."""
    with httpx.Client() as client:
        response = client.post(
            f"{WEBFLOW_BASE_URL}/collections/{collection_id}/items/publish",
            headers=_get_headers(),
            json={"itemIds": [item_id]},
        )
        response.raise_for_status()
        return response.json()
