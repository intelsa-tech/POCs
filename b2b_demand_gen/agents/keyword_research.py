"""
Agente 1: Keyword Research para B2B Demand Generation.

Usa Claude Opus 4.6 con web_search (server-side) para investigar:
- Keywords primarias y secundarias de alta intención B2B
- Volumen de búsqueda estimado y competencia
- Pain points del buyer persona
- Preguntas frecuentes (FAQ seeds)

Compatible con todos los agentes de copy: service, industry, blog.
"""

import anthropic

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Eres un experto en SEO B2B y estrategia de contenido para demand generation.
Tu especialidad es identificar keywords de alta intención de compra en el mercado B2B,
entender los pain points de compradores empresariales y mapear el customer journey.

Cuando investigues keywords para un servicio B2B:
1. Busca keywords con intención comercial/transaccional (no solo informacional)
2. Identifica long-tail keywords específicas del buyer B2B
3. Analiza qué preguntas hace el C-suite y los decision makers
4. Mapea keywords por etapa del funnel: TOFU, MOFU, BOFU
5. Considera industrias verticales relevantes

Siempre entrega resultados estructurados y accionables."""

# Prompts específicos por tipo de página
_PAGE_TYPE_INSTRUCTIONS = {
    "service": """
Enfoca la investigación en:
- Keywords de intención transaccional ("contratar", "agencia", "consultoría", "precio")
- Competidores que aparecen en búsquedas similares
- Diferenciadores que buscan los compradores B2B
- Keywords de pain point + solución""",

    "industry": """
Enfoca la investigación en:
- Keywords específicas del vertical/industria (terminología propia del sector)
- Retos y regulaciones específicas de la industria
- Benchmarks y métricas que importan en ese sector
- Casos de uso y aplicaciones concretas
- Preguntas que hacen los líderes de esa industria""",

    "blog": """
Enfoca la investigación en:
- Keywords informacionales con alto volumen de búsqueda
- Preguntas de "cómo hacer", "qué es", "mejores prácticas"
- Temas de thought leadership que busca el C-suite
- Keywords de intención educativa que alimentan el top-of-funnel
- Oportunidades de featured snippets y PAA (People Also Ask)""",
}


def run_keyword_research(
    topic: str,
    target_market: str = "B2B",
    page_type: str = "service",
) -> dict:
    """
    Ejecuta investigación de keywords para el tema dado.

    Args:
        topic: Tema/servicio/industria a investigar
        target_market: Mercado objetivo (default: "B2B")
        page_type: Tipo de página destino — "service" | "industry" | "blog"

    Returns:
        dict con la investigación completa de keywords y page_type incluido
    """
    client = anthropic.Anthropic()

    # web_search_20260209 es un tool server-side: Anthropic lo ejecuta
    # automáticamente. No requiere loop manual de tool_use.
    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
    ]

    page_instructions = _PAGE_TYPE_INSTRUCTIONS.get(page_type, _PAGE_TYPE_INSTRUCTIONS["service"])

    messages = [
        {
            "role": "user",
            "content": f"""Realiza una investigación exhaustiva de keywords para una página de tipo **{page_type}** sobre:
**Tema:** {topic}
**Mercado:** {target_market}
{page_instructions}

Investiga y entrega:

1. **Keywords Primarias** (3-5): Las más relevantes con alta intención
2. **Keywords Secundarias / LSI** (8-10): Variaciones y sinónimos importantes
3. **Long-tail Keywords** (5-8): Frases específicas de 4+ palabras
4. **Preguntas del Buyer** (5-7): Qué preguntas hacen los decision makers en Google
5. **Pain Points Detectados**: Problemas principales que buscan resolver
6. **Ángulos de Contenido**: 3 enfoques diferenciadores para la página

Usa búsquedas web para validar tendencias actuales y competencia.""",
        }
    ]

    # web_search es server-side: el stream termina con end_turn tras las búsquedas
    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    # Extraer texto final (ignorar bloques thinking)
    research_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            research_text += block.text

    return {
        "topic": topic,
        "page_type": page_type,
        "target_market": target_market,
        "research": research_text,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
