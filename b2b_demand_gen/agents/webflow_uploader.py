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
    create_collection_field,
)

MODEL = "claude-opus-4-6"

_SYSTEM_PROMPT = f"""Eres un experto en Webflow CMS y automatización de contenido para Intelsa.co.
Tu tarea es crear una nueva entrada en la Collection de Servicios de Webflow con el copy generado.

ESTRATEGIA OBLIGATORIA:
1. Si ya tienes collection_id → llama get_collection_schema directamente para ver los campos disponibles
2. Si no tienes collection_id → lista sitios → lista collections → identifica la de Servicios → get_collection_schema
3. Lee el schema de la collection para conocer los nombres EXACTOS de los campos (fieldData keys)
4. Mapea el copy_data a los campos usando EXACTAMENTE los slugs del schema:
   - copy_data.h1             → campo "h1" (PlainText)
   - copy_data.hero_subtitle  → campo "hero-subtitle" (PlainText)
   - copy_data.meta_title     → campo "meta-title" (PlainText)  [o usar como "name"]
   - copy_data.meta_description → campo "meta-description" (PlainText)
   - copy_data.cta_primary    → campo "cta-primary" (PlainText)
   - copy_data.sections       → campo "content" (RichText) — convierte a HTML
   - copy_data.faq            → campo "faq" (RichText) — convierte a HTML
   - copy_data.cta_final      → campo "cta-final" (PlainText)
   - name                     → título legible del servicio (de copy_data.h1 o topic)
   - slug                     → solo minúsculas, sin tildes, guiones (basado en topic)
5. Para campos RichText convierte el contenido a HTML limpio:
   sections → <h2>título</h2><p>cuerpo</p><h3>sub</h3><p>detalle</p>
   faq → <h3>pregunta</h3><p>respuesta</p>
6. SOLO usa campos que existen en el schema. Si un campo del copy_data no tiene campo en la collection,
   inclúyelo en el campo "content" como HTML adicional.
7. Genera el item como draft (isDraft: true) a menos que se indique publicar
8. Si auto_publish=True, publica el item con publish_page después de crearlo

IMPORTANTE: Algunos campos pueden no existir aún si el diseñador no los ha agregado.
En ese caso, consolida todo el contenido en los campos "name", "description" y "content" disponibles.
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
    template_item_id: str | None = None,
    auto_publish: bool = False,
) -> dict:
    """
    Sube el contenido generado a Webflow creando un item en la Collection CMS.

    Args:
        copywriting_output: Output del agente de copywriting
        site_id: ID del sitio Webflow (opcional, se lee de WEBFLOW_SITE_ID si no se provee)
        collection_id: ID de la Collection destino (opcional, se lee de WEBFLOW_COLLECTION_ID_{TYPE})
        template_item_id: ID de un item existente a usar como referencia de estructura (opcional)
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

    # Resolver IDs desde env vars si no se proveen
    pt_upper = page_type.upper()
    if not collection_id:
        collection_id = (
            os.environ.get(f"WEBFLOW_COLLECTION_ID_{pt_upper}")
            or os.environ.get("WEBFLOW_COLLECTION_ID", "")
        ) or None
    if not site_id:
        site_id = os.environ.get("WEBFLOW_SITE_ID", "") or None

    context_parts = []
    if site_id:
        context_parts.append(f"- **Site ID:** {site_id}")
    if collection_id:
        context_parts.append(f"- **Collection ID:** {collection_id} — usa get_collection_schema para ver los campos disponibles")
    if template_item_id:
        context_parts.append(f"- **Template Item ID:** {template_item_id} — usa get_item para inspeccionar su estructura y úsala como referencia al crear el nuevo item")
    if auto_publish:
        context_parts.append("- **Auto-publish:** Sí, publicar automáticamente al crear")
    context_str = "\n".join(context_parts) if context_parts else "- Ninguno (debes descubrir la estructura)"

    messages = [
        {
            "role": "user",
            "content": f"""Crea una nueva entrada en la Collection de Servicios de Webflow para el siguiente copy.

**Tema:** {topic}
**Tipo:** {page_type} ({page_label})

**IDs conocidos:**
{context_str}

**PASOS OBLIGATORIOS:**
1. {"Llama get_collection_schema con collection_id=" + collection_id + " para ver los campos disponibles" if collection_id else "Lista sitios → lista collections → identifica la de Servicios → llama get_collection_schema"}
2. Lee los slugs EXACTOS de los campos en el schema
3. Mapea el copy_data a los campos usando los slugs reales (ej: "h1", "hero-subtitle", "content", "faq")
4. Convierte sections a HTML para el campo RichText "content":
   <h2>título</h2><p>cuerpo</p><h3>sub</h3><p>detalle</p>
5. Convierte faq a HTML para el campo RichText "faq":
   <h3>pregunta</h3><p>respuesta</p>
6. Genera un slug limpio para el item: minúsculas, sin tildes, solo guiones
7. Crea el item con create_page (isDraft: true por defecto)
8. {"Publica inmediatamente con publish_page" if auto_publish else "Deja el item como draft"}
9. Reporta: item_id, collection_id y resumen del mapeo

**Copy generado:**
```json
{copy_summary}
```""",
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
