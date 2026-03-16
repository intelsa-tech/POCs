"""
Agente Copy: Posts de Blog B2B — Intelsa.co

Genera artículos de blog de thought leadership para posicionar a Intelsa como experta
en BPO, CX y automatización inteligente. Optimizados para SEO y LLM citation.

Usa framework AIDA (Attention-Interest-Desire-Action) para contenido educativo.

OPTIMIZACIONES DE CRÉDITOS:
- System prompt con INTELSA_PROFILE cacheado
- Schema JSON completo cacheado
- Solo el bloque dinámico (topic, keywords, idioma) consume tokens nuevos
"""

import json
import re
import anthropic
from .intelsa_context import INTELSA_PROFILE, get_language_instruction

MODEL = "claude-opus-4-6"

# ─── System prompt (CACHEADO) ─────────────────────────────────────────────────
_SYSTEM = f"""Eres un content strategist y writer B2B especializado en thought leadership
y SEO de contenidos para Intelsa.co en el espacio BPO, CX y automatización inteligente.

Tu misión es crear artículos de blog que:
1. Rankean en Google para keywords informacionales B2B de alto valor
2. Educan al comprador (COO, VP Ops, Head of CX) en su proceso de decisión
3. Posicionan a Intelsa como la experta en CX nearshore + IA
4. Generan leads calificados mediante CTAs de bajo riesgo

Principios de escritura para blogs B2B de Intelsa:
- Framework AIDA: hook que captura atención → datos que generan interés → visión del futuro posible → CTA de bajo riesgo
- Hook poderoso en los primeros 150 palabras (por qué leer esto AHORA, qué aprenderán)
- Estructura clara con H2/H3 que permita escaneo rápido
- Datos, estadísticas y ejemplos concretos — NUNCA inventados
- Cada sección responde una pregunta del buyer implícita
- CTA interno sutil: el artículo lleva naturalmente hacia los servicios de Intelsa
- Longitud objetivo: 1500-2500 palabras para profundidad suficiente de ranking
- Featured snippet optimization: responder preguntas directamente en los primeros párrafos

El artículo NO es un pitch de ventas. Es contenido genuinamente útil que
demuestra expertise y genera confianza en Intelsa como líder en CX + IA.
{INTELSA_PROFILE}"""

# ─── Schema de salida (CACHEADO) ─────────────────────────────────────────────
_BLOG_SCHEMA = """Genera el contenido completo para un ARTÍCULO DE BLOG B2B de Intelsa.co.

Usa el framework AIDA: Attention (hook) → Interest (datos, problem) → Desire (visión, solución) → Action (CTA suave).
Longitud objetivo: 1500-2500 palabras distribuidas en las secciones.

OUTPUT FORMAT — entrega un JSON válido con EXACTAMENTE estas claves:

{
  "meta_title": "60-70 chars, keyword primaria al inicio, formato: 'Keyword: subtítulo', solo primera mayúscula",
  "meta_description": "max 155 chars, incluye keyword y hook que invite al clic, sin exclamaciones",
  "focus_keyword": "La keyword primaria en la que se enfoca el artículo",
  "secondary_keywords": ["keyword 2", "keyword 3", "keyword 4"],
  "h1": "Título del artículo — atractivo, con keyword, max 70 chars, solo primera mayúscula",
  "hero_subtitle": "Subtítulo opcional que amplía el título (1 oración)",
  "reading_time": "Tiempo estimado (ej: '8 min de lectura')",
  "intro_paragraph": "150-200 palabras — hook AIDA: establece el problema, cita dato real si aplica, promete lo que aprenderán, incluye keyword primaria de forma natural",
  "cta_primary": "CTA de bajo riesgo que conecta el tema con Intelsa",
  "sections": [
    {
      "h2": "Título de sección — primera letra mayúscula, NO title case",
      "body": "200-350 palabras. Dato o estadística real si existe. Ejemplo concreto. Takeaway accionable al final.",
      "h3_items": [
        {
          "h3": "Subtítulo si la sección lo amerita",
          "body": "Detalle de la subsección"
        }
      ],
      "key_insight": "Una frase destacable para callout/quote box"
    }
  ],
  "takeaways": ["Punto accionable 1", "Punto accionable 2", "Punto accionable 3"],
  "internal_cta_title": "Título del bloque CTA interno — no debe sonar como anuncio",
  "internal_cta_body": "2-3 oraciones que conectan el aprendizaje del artículo con Intelsa",
  "internal_cta_button": "Texto del CTA — bajo riesgo, específico, sin exclamaciones",
  "conclusion_body": "150-200 palabras — resume aprendizaje, refuerza propuesta de valor de Intelsa, cierra con reflexión o pregunta",
  "faq": [
    {
      "question": "Pregunta literal que busca el lector",
      "answer": "Respuesta directa (max 50 palabras) — optimizada para featured snippet"
    }
  ],
  "cta_final": "CTA de cierre del artículo",
  "category": "Categoría del blog (ej: 'BPO', 'Experiencia del cliente', 'Automatización')",
  "tags": ["tag1", "tag2", "tag3"],
  "og_description": "Descripción para LinkedIn/Twitter — más conversacional que meta_description"
}

SECCIONES REQUERIDAS (5-7 secciones):
1. El problema / contexto actual (AIDA: Attention)
2. Por qué esto importa ahora (datos de la industria, AIDA: Interest)
3. Cómo funciona la solución / mejores prácticas (AIDA: Desire — el cuerpo principal)
4. Casos concretos o ejemplos aplicados
5. Qué considerar al implementar / criterios de evaluación
6. Cómo Intelsa lo resuelve (sutil, no un pitch directo)
7. Conclusión + FAQ

REGLAS OBLIGATORIAS:
- NUNCA inventar estadísticas — omitirlas o usar "organizaciones que han implementado esto reportan..."
- NUNCA usar title case
- NUNCA usar exclamaciones
- Mínimo 6 preguntas en FAQ optimizadas para featured snippets
- El toc_items no se incluye como campo — las secciones ya lo reemplazan"""


def run_copy_blog(
    keyword_research: dict,
    company_context: str = "",
    output_language: str = "es",
) -> dict:
    """
    Genera el contenido completo para un artículo de blog B2B de Intelsa.co.

    Args:
        keyword_research: Output de run_keyword_research() con page_type="blog"
        company_context: Perspectiva/voz de la empresa, datos reales disponibles (opcional)
        output_language: Código ISO 639-1 ("es", "en", "pt", "fr", "de")

    Returns:
        dict con page_type="blog" y copy_data en el schema unificado
    """
    client = anthropic.Anthropic()

    topic = keyword_research.get("topic") or keyword_research.get("service_topic", "")
    lang = output_language or keyword_research.get("output_language", "es")
    language_instruction = get_language_instruction(lang)

    context_block = (
        f"\n**Perspectiva/voz de la empresa y datos reales disponibles:**\n{company_context}"
        if company_context
        else ""
    )

    dynamic_block = (
        f"Crea el artículo de blog completo sobre: **{topic}**\n\n"
        f"**Investigación de Keywords:**\n{keyword_research['research']}"
        f"{context_block}"
        f"{language_instruction}"
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _BLOG_SCHEMA,
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
        max_tokens=12000,
        thinking={"type": "adaptive"},
        output_config={"effort": "max"},
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
        "page_type": "blog",
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
