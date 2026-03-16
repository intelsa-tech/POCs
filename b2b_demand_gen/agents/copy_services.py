"""
Agente Copy: Páginas de Servicios BPO — Intelsa.co

Genera copy de página de servicios orientado a compradores enterprise (COO, VP Ops, Head of CX)
usando el framework PAS (Problem-Agitate-Solution) o Before-After-Bridge según aplique.

OPTIMIZACIONES DE CRÉDITOS:
- System prompt con INTELSA_PROFILE cacheado (cache_control=ephemeral)
- Schema JSON estático cacheado — no se repagan en cada request
- Solo el bloque dinámico (topic, keywords, idioma) consume tokens nuevos
"""

import json
import re
import anthropic
from .intelsa_context import INTELSA_PROFILE, get_language_instruction

MODEL = "claude-opus-4-6"

# ─── System prompt (CACHEADO) ─────────────────────────────────────────────────
_SYSTEM = f"""Eres un copywriter B2B de élite especializado en páginas de servicios BPO
y outsourcing que convierten en los mercados US y LATAM.

Frameworks que aplicas:
- Páginas de servicio: PAS (Problem-Agitate-Solution) o Before-After-Bridge
- Enfoque en el comprador que evalúa outsourcing por primera vez o cambia de proveedor
- SEO on-page semántico sin sacrificar conversión
- Estructura optimizada para LLM citation y featured snippets
{INTELSA_PROFILE}"""

# ─── Schema de salida (CACHEADO) ─────────────────────────────────────────────
# Este bloque es idéntico en todos los requests de páginas de servicios.
_SERVICE_SCHEMA = """Genera el copy completo para una PÁGINA DE SERVICIOS de Intelsa.co.

Usa el framework PAS (Problem → Agitate → Solution) o Before-After-Bridge según el tema.
El copy debe responder las 3 preguntas del comprador: ¿por qué Intelsa?, ¿por qué Colombia?, ¿por qué ahora?

OUTPUT FORMAT — entrega un JSON válido con EXACTAMENTE estas claves:

{
  "meta_title": "60-70 chars, keyword primaria al inicio, primera letra mayúscula solo",
  "meta_description": "max 155 chars, incluye keyword y beneficio concreto, sin exclamaciones",
  "h1": "Título principal — específico y orientado al comprador, primera letra mayúscula, resto minúsculas salvo nombres propios",
  "hero_subtitle": "1-2 oraciones — propuesta de valor clara, responde ¿por qué Intelsa?",
  "cta_primary": "Texto del CTA — bajo riesgo, específico, sin exclamaciones",
  "sections": [
    {
      "h2": "Sección 1 — primera letra mayúscula, resto minúsculas (rule: no title case)",
      "body": "Cuerpo de la sección (150-300 palabras). Primera definición en las primeras 2 oraciones. Framework PAS aplicado.",
      "h3_items": [
        {
          "h3": "Subsección si aplica",
          "body": "Detalle de la subsección"
        }
      ]
    }
  ],
  "faq": [
    {
      "question": "Pregunta literal del comprador",
      "answer": "Respuesta directa primero (max 50 palabras). Respuesta directa, luego detalle si es necesario."
    }
  ],
  "cta_final": "CTA de cierre — responde una pregunta específica del comprador"
}

SECCIONES REQUERIDAS (en este orden):
1. El problema / pain actual (PAS: Problem)
2. Por qué el status quo duele más de lo que parece (PAS: Agitate)
3. La solución de Intelsa — qué hacemos y cómo (PAS: Solution)
4. Qué incluye el servicio (lista de capacidades)
5. Cómo es el proceso de onboarding / qué esperar
6. Por qué Colombia / por qué nearshore (responde la objeción implícita)
7. FAQ (mínimo 6 preguntas del comprador enterprise)

REGLAS OBLIGATORIAS:
- NUNCA inventar estadísticas — usar "nuestros clientes reportan..." si no hay dato real
- NUNCA usar title case en títulos (cada palabra con mayúscula) — solo primera letra
- NUNCA usar exclamaciones en CTAs ni en ningún texto
- Responder "¿por qué Intelsa?" y "¿por qué Colombia?" en el copy, no solo en FAQ
- Los h3_items son opcionales — usar solo cuando haya sub-elementos reales que listar"""


def run_copy_services(
    keyword_research: dict,
    company_context: str = "",
    output_language: str = "es",
) -> dict:
    """
    Genera el copy completo para una página de servicios de Intelsa.co.

    Args:
        keyword_research: Output de run_keyword_research()
        company_context: Contexto adicional / datos reales disponibles (opcional)
        output_language: Código ISO 639-1 ("es", "en", "pt", "fr", "de")

    Returns:
        dict con page_type="service" y copy_data en el nuevo schema unificado
    """
    client = anthropic.Anthropic()

    topic = keyword_research.get("topic") or keyword_research.get("service_topic", "")
    lang = output_language or keyword_research.get("output_language", "es")
    language_instruction = get_language_instruction(lang)

    context_block = (
        f"\n**Datos reales disponibles (métricas, casos de éxito, testimoniales):**\n{company_context}"
        if company_context
        else ""
    )

    # Bloque DINÁMICO — cambia por request
    dynamic_block = (
        f"Crea el copy de página de servicios para: **{topic}**\n\n"
        f"**Investigación de Keywords:**\n{keyword_research['research']}"
        f"{context_block}"
        f"{language_instruction}"
    )

    messages = [
        {
            "role": "user",
            "content": [
                # Schema ESTÁTICO — se cachea (igual en todos los requests de servicio)
                {
                    "type": "text",
                    "text": _SERVICE_SCHEMA,
                    "cache_control": {"type": "ephemeral"},
                },
                # Datos DINÁMICOS — no se cachean
                {
                    "type": "text",
                    "text": dynamic_block,
                },
            ],
        }
    ]

    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    copy_text = ""
    for block in response.content:
        if hasattr(block, "text") and block.text is not None:
            copy_text += block.text

    usage = response.usage
    return {
        "topic": topic,
        "page_type": "service",
        "output_language": lang,
        "copy_data": _parse_json_response(copy_text),
        "raw_response": copy_text,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        },
    }


def _parse_json_response(text: str) -> dict:
    """Extrae y parsea el JSON de la respuesta del modelo."""
    json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_copy": text}
