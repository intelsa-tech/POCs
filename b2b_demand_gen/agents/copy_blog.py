"""
Agente Copy: Posts de Blog B2B.

Usa Claude Opus 4.6 con adaptive thinking para generar artículos de blog
optimizados para SEO y thought leadership B2B, con:
- Meta SEO (title + description)
- Título del post y hook de introducción
- Estructura con secciones (H2/H3)
- Key takeaways
- CTA interno (hacia página de servicios)
- Conclusión

El contenido está diseñado para top-of-funnel (TOFU) y atracción orgánica,
con CTAs que llevan al lector hacia páginas de servicios o industrias.

Interfaz unificada: acepta output de keyword_research y retorna
copy_data con page_type="blog".
"""

import json
import re
import anthropic

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Eres un content strategist y writer B2B especializado en thought leadership
y SEO de contenidos. Tu expertise está en crear artículos de blog que:

1. Rankean en Google para keywords informacionales B2B
2. Educan al buyer en su proceso de decisión
3. Posicionan a la empresa como experta en el tema
4. Generan leads calificados mediante CTAs estratégicos

Principios de escritura para blogs B2B:
- Hook poderoso en los primeros 150 palabras (por qué leer esto AHORA)
- Estructura clara con H2/H3 que permita escaneo rápido
- Datos, estadísticas y ejemplos concretos en cada sección
- Tono experto pero accesible (no académico, no coloquial)
- Cada sección debe tener un takeaway accionable
- CTA interno sutil: el artículo lleva naturalmente hacia el servicio
- Longitud objetivo: 1500-2500 palabras (depth suficiente para rankear)
- Featured snippet optimization: responde preguntas directamente en los primeros párrafos

El artículo NO es un pitch de ventas. Es contenido genuinamente útil que
demuestra expertise y genera confianza.
"""


def run_copy_blog(keyword_research: dict, company_context: str = "") -> dict:
    """
    Genera el copy completo para un post de blog B2B.

    Args:
        keyword_research: Output de run_keyword_research() con page_type="blog"
        company_context: Información adicional sobre la empresa/perspectiva (opcional)

    Returns:
        dict con page_type="blog" y copy_data estructurado para Webflow
    """
    client = anthropic.Anthropic()

    topic = keyword_research.get("topic") or keyword_research.get("service_topic", "")
    context_section = f"\n**Perspectiva/voz de la empresa:**\n{company_context}" if company_context else ""

    messages = [
        {
            "role": "user",
            "content": f"""Con base en esta investigación de keywords, crea el contenido completo para un
artículo de blog B2B sobre: **{topic}**.

**Investigación de Keywords:**
{keyword_research['research']}
{context_section}

Genera el contenido estructurado para Webflow con estas secciones:

---

## 1. SEO META
- **meta_title**: (60-70 chars, keyword primaria al inicio, formato: "Keyword Principal: Subtítulo")
- **meta_description**: (150-160 chars, incluye la keyword y un hook que invite al clic)
- **focus_keyword**: La keyword primaria en la que se enfoca el artículo
- **secondary_keywords**: Lista de 3-5 keywords secundarias a incluir naturalmente

## 2. POST HEADER
- **post_title**: Título del artículo (H1) — atractivo, con keyword, max 70 chars
  Formatos que funcionan: "X formas de...", "Guía completa de...", "Por qué [empresa] necesita...", "Cómo [lograr resultado] en [tiempo]"
- **post_subtitle**: Subtítulo opcional (1 oración que amplía el título)
- **reading_time**: Tiempo estimado de lectura (ej: "8 min de lectura")
- **author_bio_placeholder**: Estructura sugerida para la bio del autor

## 3. INTRODUCTION (Hook)
- **intro_paragraph**: Primer párrafo (150-200 palabras) — hook poderoso que:
  - Establece el problema/oportunidad
  - Cita una estadística impactante si aplica
  - Promete lo que el lector va a aprender
  - Incluye la keyword primaria de forma natural

## 4. TABLE OF CONTENTS
- **toc_items**: Lista de 5-7 secciones del artículo (títulos de H2)

## 5. BODY SECTIONS
- **sections**: Array de 5-7 secciones, cada una con:
  - **h2_title**: Título de la sección (H2)
  - **body**: Contenido de la sección (200-350 palabras)
    - Incluye datos/estadísticas cuando sea posible
    - Un ejemplo o caso concreto por sección
    - Subtítulos H3 si la sección lo amerita
  - **key_insight**: Una frase destacable (quote box o callout)

## 6. KEY TAKEAWAYS
- **takeaways_title**: Título ("Lo que necesitas recordar" o similar)
- **takeaways**: Lista de 4-6 puntos accionables del artículo

## 7. INTERNAL CTA
- **internal_cta_title**: Título del bloque CTA (no debe sonar como ad)
  Ejemplo: "¿Listo para implementar esto en tu empresa?"
- **internal_cta_body**: 2-3 oraciones que conectan el aprendizaje del artículo con el servicio
- **internal_cta_button**: Texto del CTA (ej: "Ver cómo lo hacemos", "Agenda una consulta")
- **internal_cta_url_suggestion**: Página de destino sugerida (ej: "/servicios/demand-generation")

## 8. CONCLUSION
- **conclusion_title**: "Conclusión" o título más creativo
- **conclusion_body**: 150-200 palabras — resume el aprendizaje, refuerza la propuesta de valor,
  y cierra con una pregunta reflexiva o llamada a la acción suave

## 9. BLOG METADATA
- **category**: Categoría del blog (ej: "Estrategia B2B", "Marketing Digital", "Demand Generation")
- **tags**: Lista de 5-8 tags relevantes
- **featured_image_alt**: Texto alt sugerido para la imagen destacada
- **og_title**: Open Graph title para redes sociales (puede diferir del meta_title)
- **og_description**: Open Graph description (más conversacional, para compartir en LinkedIn/Twitter)

---
Entrega todo en formato JSON válido con estas claves exactas.
El body de cada sección debe ser texto completo, no bullets ni esquemas.""",
        }
    ]

    with client.messages.stream(
        model=MODEL,
        max_tokens=12000,
        thinking={"type": "adaptive"},
        output_config={"effort": "max"},
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
        "page_type": "blog",
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
