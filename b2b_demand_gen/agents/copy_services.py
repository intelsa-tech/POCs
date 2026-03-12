"""
Agente Copy: Páginas de Servicios B2B.

Usa Claude Opus 4.6 con adaptive thinking para generar:
- Hero section (headline + subheadline + CTA)
- Sección de pain points
- Propuesta de valor y diferenciadores
- Detalle de servicios incluidos
- Proceso de trabajo (pasos)
- FAQ basado en keywords
- CTA final
- Meta title y meta description SEO

Interfaz unificada: acepta output de keyword_research y retorna
copy_data con page_type="service".
"""

import json
import re
import anthropic

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Eres un copywriter B2B de élite especializado en páginas de servicios
que convierten. Tienes expertise en:

- Frameworks de copywriting: AIDA, PAS (Problem-Agitate-Solution), Before-After-Bridge
- Escritura para C-suite y decision makers empresariales
- SEO on-page semántico sin sacrificar conversión
- Estructuras de páginas de servicio que generan leads calificados

Tu estilo es: directo, basado en valor de negocio, sin jerga innecesaria,
orientado a resultados medibles (ROI, pipeline, revenue).

Al escribir copy para B2B:
- Habla el idioma del negocio (ROI, pipeline, MQL, SQLs, CAC, LTV)
- Usa datos y estadísticas cuando sea posible
- El CTA principal debe crear urgencia sin ser agresivo
- El copy debe responder: "¿Por qué nosotros?" y "¿Por qué ahora?"
"""


def run_copy_services(keyword_research: dict, company_context: str = "") -> dict:
    """
    Genera el copy completo para una página de servicios B2B.

    Args:
        keyword_research: Output de run_keyword_research()
        company_context: Información adicional sobre la empresa/servicio (opcional)

    Returns:
        dict con page_type="service" y copy_data estructurado para Webflow
    """
    client = anthropic.Anthropic()

    topic = keyword_research.get("topic") or keyword_research.get("service_topic", "")
    context_section = f"\n**Contexto de la empresa:**\n{company_context}" if company_context else ""

    messages = [
        {
            "role": "user",
            "content": f"""Con base en esta investigación de keywords, crea el copy completo para una
página de servicios de {topic}.

**Investigación de Keywords:**
{keyword_research['research']}
{context_section}

Genera el copy estructurado para Webflow con estas secciones:

---

## 1. SEO META
- **meta_title**: (60-70 chars, incluye keyword primaria)
- **meta_description**: (150-160 chars, incluye CTA implícito)

## 2. HERO SECTION
- **hero_headline**: Headline principal (max 10 palabras, high-impact)
- **hero_subheadline**: Subheadline explicativo (1-2 oraciones, propuesta de valor clara)
- **hero_cta_primary**: Texto del botón CTA principal
- **hero_cta_secondary**: Texto del botón CTA secundario (más suave)

## 3. PAIN POINTS SECTION
- **pain_section_title**: Título de la sección
- **pain_points**: Lista de 3-4 pain points con descripción corta cada uno

## 4. PROPUESTA DE VALOR
- **value_prop_title**: Título de la sección
- **value_prop_body**: 2-3 párrafos que explican el servicio y diferenciadores
- **value_metrics**: 3 métricas de impacto (ej: "300% más MQLs", "60 días para ver resultados")

## 5. SERVICIOS / QUÉ INCLUYE
- **services_title**: Título de la sección
- **services**: Lista de 4-6 servicios con nombre + descripción corta (1 oración)

## 6. PROCESO / CÓMO TRABAJAMOS
- **process_title**: Título de la sección
- **process_steps**: 4 pasos del proceso con nombre + descripción

## 7. FAQ
- **faq_title**: Título de la sección
- **faqs**: 5 preguntas y respuestas basadas en las keywords de pregunta identificadas

## 8. CTA FINAL
- **cta_section_title**: Headline de la sección final
- **cta_section_body**: 1-2 oraciones de cierre
- **cta_final_button**: Texto del botón CTA final

---
Entrega todo en formato JSON válido con estas claves exactas.""",
        }
    ]

    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    copy_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            copy_text += block.text

    copy_data = _parse_json_response(copy_text)

    return {
        "topic": topic,
        "page_type": "service",
        "copy_data": copy_data,
        "raw_response": copy_text,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
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
    # Fallback: intentar parsear toda la respuesta como JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_copy": text}
