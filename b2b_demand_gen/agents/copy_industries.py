"""
Agente Copy: Páginas de Industrias B2B.

Usa Claude Opus 4.6 con adaptive thinking para generar copy específico
de un vertical/industria, con:
- Hero orientado a los retos únicos de esa industria
- Sección de desafíos del sector
- Casos de uso y aplicaciones concretas
- Por qué nuestra solución encaja en esta industria
- Métricas de impacto relevantes al sector
- Testimonios/social proof placeholder
- FAQ con terminología de la industria
- CTA final

Interfaz unificada: acepta output de keyword_research y retorna
copy_data con page_type="industry".
"""

import json
import re
import anthropic

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Eres un copywriter B2B especializado en marketing de verticales e industrias.
Tu expertise está en conectar soluciones B2B con los retos específicos de cada sector.

Al escribir copy para una página de industria:
- Usa la terminología propia del sector (no jerga genérica de marketing)
- Demuestra conocimiento profundo de los pain points del vertical
- Referencia regulaciones, estándares o tendencias de la industria cuando sea relevante
- Habla de métricas y KPIs que importan EN ESA INDUSTRIA (no métricas genéricas)
- El buyer persona puede ser muy específico (CIO en manufactura vs. CMO en SaaS): adáptate
- Usa casos de uso concretos y aplicaciones reales, no conceptos abstractos
- El tono debe transmitir: "Entendemos tu industria mejor que nadie"

Principios de copywriting B2B para páginas de industria:
- Specificity sells: cuanto más específico al sector, más credibilidad
- Muestra el costo del status quo (no hacer nada)
- Referencia competidores del sector si aplica
- Social proof debe ser del mismo vertical siempre que sea posible
"""


def run_copy_industries(keyword_research: dict, company_context: str = "") -> dict:
    """
    Genera el copy completo para una página de industria B2B.

    Args:
        keyword_research: Output de run_keyword_research() con page_type="industry"
        company_context: Información adicional sobre la empresa/servicio (opcional)

    Returns:
        dict con page_type="industry" y copy_data estructurado para Webflow
    """
    client = anthropic.Anthropic()

    topic = keyword_research.get("topic") or keyword_research.get("service_topic", "")
    context_section = f"\n**Contexto de la empresa:**\n{company_context}" if company_context else ""

    messages = [
        {
            "role": "user",
            "content": f"""Con base en esta investigación de keywords, crea el copy completo para una
página de industria dirigida al vertical: **{topic}**.

**Investigación de Keywords:**
{keyword_research['research']}
{context_section}

Genera el copy estructurado para Webflow con estas secciones:

---

## 1. SEO META
- **meta_title**: (60-70 chars, incluye nombre de la industria + solución)
- **meta_description**: (150-160 chars, menciona el sector y el beneficio clave)

## 2. HERO SECTION
- **hero_headline**: Headline específico para esta industria (max 12 palabras)
  Ejemplo: "Acelera el pipeline de ventas en [Industria] con IA"
- **hero_subheadline**: 1-2 oraciones explicando el valor específico para este vertical
- **hero_cta_primary**: CTA principal (orientado al sector)
- **hero_cta_secondary**: CTA secundario (más educativo/informacional)

## 3. INDUSTRY CHALLENGES
- **challenges_title**: Título de la sección ("Los retos de [Industria] que frenан tu crecimiento")
- **challenges**: Lista de 4-5 desafíos específicos de esta industria con descripción corta

## 4. OUR APPROACH FOR THIS INDUSTRY
- **approach_title**: Título ("Cómo resolvemos los retos de [Industria]")
- **approach_body**: 2-3 párrafos explicando la metodología adaptada al sector
- **approach_differentiators**: 3-4 diferenciadores específicos para esta industria

## 5. USE CASES
- **use_cases_title**: Título de la sección
- **use_cases**: Lista de 3-4 casos de uso concretos con:
  - nombre del caso de uso
  - descripción del problema
  - cómo se resuelve
  - resultado esperado

## 6. INDUSTRY METRICS
- **metrics_title**: Título ("Resultados en [Industria]")
- **industry_metrics**: 3 métricas relevantes para ESTE sector
  (ej: "40% reducción en ciclo de venta para SaaS", "2x más demos en manufactura")

## 7. SOCIAL PROOF
- **social_proof_title**: Título de la sección
- **testimonial_placeholder**: Estructura de testimonio con campos: quote, name, role, company, industry
- **logos_section_title**: "Empresas de [Industria] que confían en nosotros"

## 8. FAQ INDUSTRY-SPECIFIC
- **faq_title**: Título
- **faqs**: 4-5 preguntas específicas de esta industria (no preguntas genéricas)

## 9. CTA FINAL
- **cta_section_title**: Headline final orientado a la industria
- **cta_section_body**: 1-2 oraciones de cierre con urgencia sector-específica
- **cta_final_button**: Texto del CTA (personalizado para el sector)

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
        if hasattr(block, "text") and block.text is not None:
            copy_text += block.text

    copy_data = _parse_json_response(copy_text)

    return {
        "topic": topic,
        "page_type": "industry",
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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_copy": text}
