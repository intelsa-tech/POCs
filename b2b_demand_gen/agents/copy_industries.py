"""
Agente Copy: Páginas de Industrias/Verticales BPO — Intelsa.co

Genera copy específico de un vertical/industria, conectando los retos de CX y operaciones
del sector con la solución BPO+IA de Intelsa.

OPTIMIZACIONES DE CRÉDITOS:
- System prompt con INTELSA_PROFILE cacheado
- Schema JSON estático cacheado
- Solo el bloque dinámico (industry, keywords, idioma) consume tokens nuevos
"""

import json
import re
import anthropic
from .intelsa_context import INTELSA_PROFILE, get_language_instruction

MODEL = "claude-opus-4-6"

# ─── System prompt (CACHEADO) ─────────────────────────────────────────────────
_SYSTEM = f"""Eres un copywriter B2B especializado en marketing de verticales para el sector
BPO, outsourcing de CX y automatización inteligente.

Tu expertise: conectar los retos específicos de cada industria con la solución de
Intelsa (IA + talento humano bilingüe nearshore).

Al escribir copy para una página de industria:
- Usa la terminología propia del sector — no jerga genérica de marketing
- Demuestra conocimiento profundo de los pain points de CX y operaciones del vertical
- Habla de métricas que importan EN ESA INDUSTRIA (CSAT, AHT, FCR, NPS, costo por ticket)
- El buyer persona puede variar mucho: VP Ops de retail vs. Head of CX de fintech
- El tono debe transmitir: "Entendemos tu industria y sus retos operacionales"
- Usa casos de uso concretos de omnicanalidad y automatización para ese vertical
- Specificity sells: cuanto más específico al sector, más credibilidad
{INTELSA_PROFILE}"""

# ─── Schema de salida (CACHEADO) ─────────────────────────────────────────────
_INDUSTRY_SCHEMA = """Genera el copy completo para una PÁGINA DE INDUSTRIA de Intelsa.co.

La página debe demostrar que Intelsa entiende los retos únicos de CX y operaciones
de esta industria mejor que un BPO genérico.

OUTPUT FORMAT — entrega un JSON válido con EXACTAMENTE estas claves:

{
  "meta_title": "60-70 chars, incluye nombre de la industria + solución BPO, solo primera mayúscula",
  "meta_description": "max 155 chars, menciona el sector y el beneficio clave, sin exclamaciones",
  "h1": "Título específico para este vertical — primera letra mayúscula, resto minúsculas",
  "hero_subtitle": "1-2 oraciones — valor específico para esta industria, responde ¿por qué Intelsa para [industria]?",
  "cta_primary": "CTA orientado al sector — bajo riesgo, específico",
  "sections": [
    {
      "h2": "Sección — primera letra mayúscula, no title case",
      "body": "Cuerpo (150-300 palabras). Específico al sector, con terminología propia.",
      "h3_items": [
        {
          "h3": "Subsección si aplica",
          "body": "Detalle"
        }
      ]
    }
  ],
  "faq": [
    {
      "question": "Pregunta específica de este sector",
      "answer": "Respuesta directa primero (max 50 palabras)"
    }
  ],
  "cta_final": "CTA de cierre — personalizado para el sector"
}

SECCIONES REQUERIDAS (en este orden):
1. Los retos de [industria] que frenan las operaciones de CX (Pain points del sector)
2. Cómo afecta al negocio no resolver esto (costo del status quo)
3. La solución de Intelsa para [industria] — metodología adaptada al sector
4. Casos de uso concretos: 3-4 escenarios reales del sector con resultado esperado
5. Métricas de impacto relevantes para este sector (no genéricas)
6. Por qué Intelsa entiende [industria] (experiencia, certificaciones relevantes)
7. FAQ específico del sector (mínimo 6 preguntas — no preguntas genéricas de BPO)

REGLAS OBLIGATORIAS:
- NUNCA inventar estadísticas — usar "en el sector [X], nuestros clientes reportan..."
- NUNCA usar title case en títulos — solo primera letra mayúscula
- NUNCA usar exclamaciones
- Los KPIs y benchmarks deben ser los que usa realmente esa industria
- Social proof y casos de uso deben hacer referencia al mismo vertical"""


def run_copy_industries(
    keyword_research: dict,
    company_context: str = "",
    output_language: str = "es",
) -> dict:
    """
    Genera el copy completo para una página de industria de Intelsa.co.

    Args:
        keyword_research: Output de run_keyword_research() con page_type="industry"
        company_context: Datos reales disponibles para este vertical (opcional)
        output_language: Código ISO 639-1 ("es", "en", "pt", "fr", "de")

    Returns:
        dict con page_type="industry" y copy_data en el schema unificado
    """
    client = anthropic.Anthropic()

    topic = keyword_research.get("topic") or keyword_research.get("service_topic", "")
    lang = output_language or keyword_research.get("output_language", "es")
    language_instruction = get_language_instruction(lang)

    context_block = (
        f"\n**Datos reales del sector disponibles:**\n{company_context}"
        if company_context
        else ""
    )

    dynamic_block = (
        f"Crea el copy de página de industria para el vertical: **{topic}**\n\n"
        f"**Investigación de Keywords del Sector:**\n{keyword_research['research']}"
        f"{context_block}"
        f"{language_instruction}"
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _INDUSTRY_SCHEMA,
                    "cache_control": {"type": "ephemeral"},
                },
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
        "page_type": "industry",
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
