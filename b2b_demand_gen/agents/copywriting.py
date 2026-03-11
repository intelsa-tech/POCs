"""
Agente 2: Copywriting para página de servicios B2B Demand Generation.

Usa Claude Opus 4.6 con adaptive thinking para generar:
- Hero section (headline + subheadline + CTA)
- Sección de propuesta de valor
- Sección de servicios/beneficios
- Social proof / testimonios placeholder
- FAQ basado en keywords
- Meta title y meta description SEO
"""

import anthropic

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Eres un copywriter B2B de élite especializado en demand generation y páginas de servicios
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


def run_copywriting(keyword_research: dict, company_context: str = "") -> dict:
    """
    Genera el copy completo para la página de servicios B2B.

    Args:
        keyword_research: Output del agente de keyword research
        company_context: Información adicional sobre la empresa/servicio (opcional)

    Returns:
        dict con el copy estructurado listo para Webflow
    """
    client = anthropic.Anthropic()

    context_section = f"\n**Contexto de la empresa:**\n{company_context}" if company_context else ""

    messages = [
        {
            "role": "user",
            "content": f"""Con base en esta investigación de keywords, crea el copy completo para una
página de servicios de {keyword_research['service_topic']}.

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

    # Usar adaptive thinking para copywriting de calidad
    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    # Extraer el copy generado
    copy_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            copy_text += block.text

    # Intentar parsear como JSON para validación
    import json
    import re

    copy_data = {}
    # Buscar JSON en la respuesta
    json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", copy_text)
    if json_match:
        try:
            copy_data = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    if not copy_data:
        # Si no hay JSON válido, retornar el texto raw para revisión manual
        copy_data = {"raw_copy": copy_text}

    return {
        "service_topic": keyword_research["service_topic"],
        "copy_data": copy_data,
        "raw_response": copy_text,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
