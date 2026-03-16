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
import os
import anthropic
from .intelsa_context import INTELSA_PROFILE
from tools.webflow_api import (
    list_sites,
    list_collections,
    get_collection,
    get_item,
    list_collection_items,
    create_collection_item,
    publish_item,
)

MODEL = "claude-opus-4-6"

# ID del item template cuyo diseño queremos replicar (puede sobrescribirse con env var)
_TEMPLATE_ITEM_SLUG = "servicio-atencion-cliente"

_SYSTEM_PROMPT = f"""Eres un experto en Webflow CMS y automatización de contenido para Intelsa.co.
Tu tarea es crear una página nueva en Webflow que use EXACTAMENTE el mismo diseño que la página
template existente de Intelsa (slug: {_TEMPLATE_ITEM_SLUG}).

ESTRATEGIA OBLIGATORIA:
1. Lista los sitios y obtén el site_id
2. Lista las collections del sitio
3. Busca el item template con slug "{_TEMPLATE_ITEM_SLUG}" en la collection de Servicios:
   - Llama list_collection_items en la collection que parezca ser "Servicios"
   - Identifica cuál item tiene slug == "{_TEMPLATE_ITEM_SLUG}"
   - Llama get_item con ese collection_id e item_id para obtener sus campos EXACTOS
4. Usa los nombres de campo EXACTOS del template (fieldData) para crear el nuevo item
   - NO inventes nombres de campo ni uses nombres genéricos
   - Usa SOLO los campos que existen en el template
   - Si un campo es Rich Text, usa HTML válido
   - Si un campo acepta listas/arrays, usa el mismo formato que el template
5. Genera un slug limpio para el nuevo item basado en el topic (solo minúsculas, sin tildes, guiones)
6. Crea el item en la MISMA collection que el template — así heredará el mismo diseño/template
7. Si auto_publish=True, publica el item inmediatamente

MAPEO DE CAMPOS (copy_data → campos del template):
- h1 → campo de título/heading principal del template
- hero_subtitle → campo de subtítulo/descripción corta
- meta_description → campo de meta description o description
- cta_primary → campo de CTA o botón principal
- sections[0].h2 + sections[0].body → primer bloque de contenido
- sections completo → campo de contenido rico (Rich Text) o secciones individuales
- faq → campo de preguntas frecuentes (si existe) o parte del Rich Text
- cta_final → campo de CTA final o parte del contenido

Para campos Rich Text, convierte el contenido a HTML estructurado:
<h2>título</h2><p>párrafo</p><h3>subtítulo</h3><p>párrafo</p>

IMPORTANTE: Siempre crea el item como draft (isDraft: true) a menos que se indique explícitamente publicar.
{INTELSA_PROFILE}"""

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
        "name": "get_item",
        "description": "Obtiene un item específico de una Collection por su ID. Úsalo para leer el item template y ver sus campos exactos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "ID de la Collection",
                },
                "item_id": {
                    "type": "string",
                    "description": "ID del item a obtener",
                },
            },
            "required": ["collection_id", "item_id"],
        },
    },
    {
        "name": "list_collection_items",
        "description": "Lista items existentes en una Collection para encontrar el item template por slug.",
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
        elif tool_name == "get_item":
            result = get_item(tool_input["collection_id"], tool_input["item_id"])
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

    template_item_id = os.environ.get("WEBFLOW_TEMPLATE_ITEM_ID", "")
    template_hint = (
        f"- **Template Item ID conocido:** {template_item_id}"
        if template_item_id else
        f'- Busca el item template con slug "{_TEMPLATE_ITEM_SLUG}" listando items de la collection de Servicios'
    )

    messages = [
        {
            "role": "user",
            "content": f"""Crea una nueva {page_label} en Webflow usando el mismo diseño que la página template existente.

**Tema del nuevo servicio:** {topic}
**Tipo de página:** {page_type} ({page_label})

**IDs conocidos:**
{context_str}
{template_hint}

**PASOS OBLIGATORIOS:**
1. Lista los sitios → obtén site_id
2. Lista las collections del sitio
3. {"Usa collection_id: " + collection_id + " directamente" if collection_id else 'Identifica la collection de Servicios (busca "Servicio", "Services" o similar en el nombre/slug)'}
4. Llama list_collection_items en esa collection para encontrar el item con slug "{_TEMPLATE_ITEM_SLUG}"
5. {"Llama get_item(collection_id='" + collection_id + "', item_id='" + template_item_id + "') para ver los campos exactos del template" if template_item_id else f'Llama get_item con el collection_id y el item_id del template "{_TEMPLATE_ITEM_SLUG}"'}
6. Usa los nombres de campo EXACTOS del template para mapear el nuevo copy
7. Crea el nuevo item en la MISMA collection con esos campos exactos
8. {'Publica el item inmediatamente con publish_page' if auto_publish else 'Deja el item como isDraft: true'}
9. Reporta: item_id, collection_id, URL (si disponible) y resumen del mapeo de campos

**Copy generado para el nuevo servicio:**
```json
{copy_summary}
```

RECUERDA: El objetivo es que la nueva página use el mismo template de diseño que "{_TEMPLATE_ITEM_SLUG}". Esto se logra creando el item en la misma Collection con los mismos nombres de campo.""",
        }
    ]

    # Agentic loop con tool use
    max_iterations = 15
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
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

    usage = response.usage
    return {
        "topic": topic,
        "page_type": page_type,
        "result": final_text,
        "iterations": iteration,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        },
    }
