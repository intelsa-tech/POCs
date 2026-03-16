"""
Agente 3: Webflow Uploader para B2B Demand Generation.

Usa Claude Opus 4.6 con tool use para:
1. Descubrir sitios y Collections disponibles en Webflow
2. Identificar el template/Collection correcto según el tipo de página
3. Mapear el copy generado a los campos de Webflow
4. Crear el item en la Collection (como draft para revisión)
5. Opcionalmente publicar el item

Compatible con todos los agentes de copy: service, industry, blog.
"""

import json
import anthropic
from tools.webflow_api import (
    list_sites,
    list_collections,
    get_collection,
    list_collection_items,
    create_collection_item,
    publish_item,
)

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Eres un experto en Webflow CMS y automatización de contenido.
Tu tarea es subir contenido de marketing B2B a Webflow de forma precisa.

Al trabajar con Webflow:
1. Primero explora los sitios y collections disponibles
2. Identifica el collection más apropiado según el tipo de página (servicio, industria o blog)
3. Analiza el schema del collection (campos disponibles)
4. Mapea el copy generado a los campos correctos del collection
5. Crea el item como DRAFT para que el equipo pueda revisarlo antes de publicar
6. Confirma la creación exitosa con el URL del item

IMPORTANTE: Siempre crea el item como draft (isDraft: true) a menos que se indique explícitamente publicar."""

# Definición de tools para el agente Webflow
WEBFLOW_TOOLS = [
    {
        "name": "list_sites",
        "description": "Lista todos los sitios Webflow disponibles con el API token actual.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_collections",
        "description": "Lista todas las Collections (CMS) de un sitio Webflow específico.",
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {
                    "type": "string",
                    "description": "ID del sitio Webflow",
                }
            },
            "required": ["site_id"],
        },
    },
    {
        "name": "get_collection_schema",
        "description": "Obtiene el schema completo de una Collection, incluyendo todos sus campos y tipos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "ID de la Collection de Webflow",
                }
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "list_collection_items",
        "description": "Lista items existentes en una Collection para entender el formato de datos esperado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "ID de la Collection",
                },
                "limit": {
                    "type": "integer",
                    "description": "Número de items a listar (default: 3)",
                    "default": 3,
                },
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "create_page",
        "description": "Crea una nueva página/item en una Collection de Webflow con el contenido proporcionado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "ID de la Collection donde se creará el item",
                },
                "field_data": {
                    "type": "object",
                    "description": "Datos del item. Debe incluir 'name' y 'slug' como mínimo, más los campos específicos del template.",
                },
            },
            "required": ["collection_id", "field_data"],
        },
    },
    {
        "name": "publish_page",
        "description": "Publica un item draft en Webflow para hacerlo visible en el sitio. SOLO usar cuando se confirme explícitamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "ID de la Collection",
                },
                "item_id": {
                    "type": "string",
                    "description": "ID del item a publicar",
                },
            },
            "required": ["collection_id", "item_id"],
        },
    },
]


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """Ejecuta un tool de Webflow y retorna el resultado como string JSON."""
    try:
        if tool_name == "list_sites":
            result = list_sites()
        elif tool_name == "list_collections":
            result = list_collections(tool_input["site_id"])
        elif tool_name == "get_collection_schema":
            result = get_collection(tool_input["collection_id"])
        elif tool_name == "list_collection_items":
            result = list_collection_items(
                tool_input["collection_id"],
                tool_input.get("limit", 3),
            )
        elif tool_name == "create_page":
            result = create_collection_item(
                tool_input["collection_id"],
                tool_input["field_data"],
            )
        elif tool_name == "publish_page":
            result = publish_item(
                tool_input["collection_id"],
                tool_input["item_id"],
            )
        else:
            result = {"error": f"Tool desconocido: {tool_name}"}

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_webflow_upload(
    copywriting_output: dict,
    site_id: str | None = None,
    collection_id: str | None = None,
    auto_publish: bool = False,
) -> dict:
    """
    Sube el contenido generado a Webflow.

    Args:
        copywriting_output: Output del agente de copywriting
        site_id: ID del sitio Webflow (opcional, el agente lo descubrirá si no se provee)
        collection_id: ID de la Collection destino (opcional)
        auto_publish: Si True, publica el item automáticamente (default: False)

    Returns:
        dict con el resultado de la subida y el URL del item creado
    """
    client = anthropic.Anthropic()

    # Soporte para la interfaz antigua (service_topic) y la nueva (topic + page_type)
    topic = copywriting_output.get("topic") or copywriting_output.get("service_topic", "")
    page_type = copywriting_output.get("page_type", "service")

    page_type_labels = {
        "service": "página de servicios",
        "industry": "página de industria",
        "blog": "artículo de blog",
    }
    page_label = page_type_labels.get(page_type, "página")

    copy_summary = json.dumps(copywriting_output["copy_data"], ensure_ascii=False, indent=2)
    if len(copy_summary) > 3000:
        copy_summary = copy_summary[:3000] + "\n... [truncado para el contexto]"

    context_parts = []
    if site_id:
        context_parts.append(f"- **Site ID conocido:** {site_id}")
    if collection_id:
        context_parts.append(f"- **Collection ID conocido:** {collection_id}")
    if auto_publish:
        context_parts.append("- **Auto-publish:** Sí, publicar automáticamente al crear")

    context_str = "\n".join(context_parts) if context_parts else "- Ninguno (debes descubrir la estructura)"

    messages = [
        {
            "role": "user",
            "content": f"""Sube esta {page_label} B2B a Webflow.

**Tema:** {topic}
**Tipo de página:** {page_type} ({page_label})

**Contexto previo:**
{context_str}

**Copy generado (a subir):**
```json
{copy_summary}
```

Pasos a seguir:
1. {'Usa el collection_id conocido directamente' if collection_id else f'Lista los sitios disponibles y encuentra la Collection apropiada para una {page_label}'}
2. {'Explora el schema del collection' if not collection_id else 'Verifica el schema del collection para mapear campos'}
3. Mapea el copy a los campos del collection (adapta los nombres de campo al schema real)
4. Crea el item como DRAFT con toda la información
5. {'Publica el item después de crearlo' if auto_publish else 'Deja el item como DRAFT para revisión'}
6. Reporta el ID del item creado y próximos pasos""",
        }
    ]

    # Agentic loop con tool use
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=SYSTEM_PROMPT,
            tools=WEBFLOW_TOOLS,
            messages=messages,
        )

        # Si Claude terminó, salir del loop
        if response.stop_reason == "end_turn":
            break

        # Procesar tool calls
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [Webflow Tool] {block.name}({json.dumps(block.input, ensure_ascii=False)[:100]}...)")
                    result = _execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # stop_reason inesperado
            break

    # Extraer respuesta final
    final_text = ""
    for block in response.content:
        if hasattr(block, "text") and block.text is not None:
            final_text += block.text

    return {
        "topic": topic,
        "page_type": page_type,
        "result": final_text,
        "iterations": iteration,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
