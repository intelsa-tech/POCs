"""
Agente 1: Keyword Research para B2B Demand Generation — Intelsa.co

Usa Claude Opus 4.6 con web_search (server-side) para investigar:
- Keywords de alta intención de compra (transaccional/comercial) por tipo de página
- Pain points de compradores B2B de BPO/CX
- Volúmenes y tendencias reales vía búsquedas web

OPTIMIZACIONES DE CRÉDITOS:
- System prompt marcado con cache_control=ephemeral (se cachea ~5 min)
- Instrucciones estáticas por page_type marcadas como cacheadas
- Solo el bloque dinámico (topic, market, language) consume tokens nuevos
"""

import anthropic
from .intelsa_context import INTELSA_PROFILE, get_language_instruction

MODEL = "claude-opus-4-6"

# ─── System prompt (CACHEADO) ────────────────────────────────────────────────
_SYSTEM = f"""Eres un experto en SEO B2B y estrategia de contenido para demand generation
en el sector BPO, outsourcing de CX y automatización inteligente.

Tu especialidad es identificar keywords de alta intención de compra para empresas
como Intelsa que venden servicios BPO nearshore a compradores enterprise en EE.UU. y LATAM.

Principios de investigación:
1. Prioriza keywords con intención comercial/transaccional sobre informacional
2. Identifica long-tail keywords específicas del buyer B2B (COO, VP Ops, Head of CX)
3. Analiza qué preguntas hace el C-suite al evaluar proveedores BPO
4. Mapea keywords por etapa del funnel: TOFU, MOFU, BOFU
5. Considera diferencias de mercado: EE.UU. (inglés) vs LATAM (español)
6. Busca oportunidades de featured snippets y PAA (People Also Ask)

Siempre entrega resultados estructurados, accionables y basados en búsquedas reales.
{INTELSA_PROFILE}"""

# ─── Instrucciones estáticas por page_type (CACHEADAS) ────────────────────────
# Estas instrucciones no cambian entre requests del mismo tipo → se cachean.
_PAGE_TYPE_INSTRUCTIONS: dict[str, str] = {
    "service": """Investiga keywords para una PÁGINA DE SERVICIOS BPO/CX.

ENFOQUE:
- Keywords de intención transaccional: "outsourcing customer service", "contratar BPO",
  "contact center nearshore", "externalizar atención al cliente"
- Keywords de comparación: "BPO Colombia vs Filipinas", "costos outsourcing CX"
- Keywords de problema + solución: "reducir costos atención cliente", "mejorar CSAT"
- Keywords de proveedor: "mejor BPO nearshore", "contact center con IA"
- Long-tail de comprador enterprise: "outsource bilingual customer support team"

ESTRUCTURA DE ENTREGA OBLIGATORIA:
1. **Keywords Primarias** (3-5): Mayor intención transaccional, alta relevancia
2. **Keywords Secundarias / LSI** (8-10): Variaciones semánticas y sinónimos
3. **Long-tail Keywords** (5-8): Frases de 4+ palabras con intención de compra
4. **Preguntas del Buyer** (6-8): Preguntas reales que hacen los decisores en Google
5. **Pain Points Detectados**: Problemas principales que motivan la búsqueda
6. **Ángulos de Contenido**: 3 enfoques diferenciadores para posicionar la página
7. **Análisis de Competencia**: 2-3 competidores que aparecen en estas búsquedas""",

    "industry": """Investiga keywords para una PÁGINA DE INDUSTRIA/VERTICAL BPO.

ENFOQUE:
- Keywords del vertical con terminología propia del sector
- Retos de CX y operaciones específicos de esa industria
- Benchmarks y métricas que importan en ese sector (CSAT, NPS, FCR, AHT por industria)
- Casos de uso de BPO y automatización específicos del vertical
- Regulaciones o estándares del sector que afecten CX (HIPAA en salud, PCI en fintech)
- Preguntas que hacen los líderes de operaciones/CX en esa industria

ESTRUCTURA DE ENTREGA OBLIGATORIA:
1. **Keywords Primarias del Vertical** (3-5): Más relevantes para el sector
2. **Keywords Secundarias / LSI** (8-10): Variaciones y términos del sector
3. **Long-tail Keywords** (5-8): Con nombre del vertical + solución BPO
4. **Preguntas del Buyer en este Sector** (6-8): Lo que preguntan los COO/VP Ops del vertical
5. **Pain Points Específicos del Sector**: Desafíos de CX únicos de esta industria
6. **Ángulos de Contenido**: 3 enfoques para posicionar la página de industria
7. **Métricas Clave del Sector**: KPIs que importan en esta industria""",

    "blog": """Investiga keywords para un ARTÍCULO DE BLOG B2B educativo/thought leadership.

ENFOQUE:
- Keywords informacionales con alto volumen de búsqueda
- Preguntas de "cómo hacer", "qué es", "cuánto cuesta", "mejores prácticas" en BPO/CX
- Temas de thought leadership para COOs, CX Directors y CFOs
- Keywords educativas para top-of-funnel del mercado BPO/Contact Center
- Oportunidades de featured snippets (respuestas directas en 40-50 palabras)
- Temas que posicionen a Intelsa como experta en CX inteligente + IA

ESTRUCTURA DE ENTREGA OBLIGATORIA:
1. **Keyword Principal del Artículo** (1): La keyword central con mayor potencial de ranking
2. **Keywords Secundarias** (6-8): Para incluir naturalmente en el texto
3. **Long-tail / Featured Snippet Keywords** (5-7): Preguntas para responder directamente
4. **PAA (People Also Ask)** (5-7): Preguntas relacionadas que aparecen en Google
5. **Ángulo del Artículo**: El enfoque más diferenciado y con mejor oportunidad de ranking
6. **Estructura Sugerida**: 5-6 H2 que cubran las keywords de forma natural
7. **Competencia en SERP**: Qué tipo de contenido rankea actualmente (guías, comparaciones, etc.)""",
}


def run_keyword_research(
    topic: str,
    target_market: str = "empresas B2B medianas y grandes",
    page_type: str = "service",
    output_language: str = "es",
) -> dict:
    """
    Ejecuta investigación de keywords con prompt caching activado.

    Args:
        topic: Tema/servicio/industria a investigar
        target_market: Mercado objetivo
        page_type: "service" | "industry" | "blog"
        output_language: Código ISO 639-1 ("es", "en", "pt", "fr", "de")

    Returns:
        dict con la investigación y metadata de uso (incluyendo tokens cacheados)
    """
    client = anthropic.Anthropic()

    tools = [{"type": "web_search_20260209", "name": "web_search"}]

    page_instructions = _PAGE_TYPE_INSTRUCTIONS.get(
        page_type, _PAGE_TYPE_INSTRUCTIONS["service"]
    )
    language_instruction = get_language_instruction(output_language)

    # Bloque DINÁMICO — cambia por request, NO se cachea
    dynamic_block = (
        f"Realiza una investigación exhaustiva de keywords para:\n\n"
        f"**Tema / Servicio:** {topic}\n"
        f"**Tipo de página:** {page_type}\n"
        f"**Mercado objetivo:** {target_market}\n"
        f"{language_instruction}\n\n"
        f"Usa búsquedas web para validar tendencias reales, volúmenes estimados "
        f"y competencia actual en los SERPs."
    )

    messages = [
        {
            "role": "user",
            "content": [
                # Bloque ESTÁTICO por page_type — se cachea
                {
                    "type": "text",
                    "text": page_instructions,
                    "cache_control": {"type": "ephemeral"},
                },
                # Bloque DINÁMICO — no se cachea
                {
                    "type": "text",
                    "text": dynamic_block,
                },
            ],
        }
    ]

    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        # System prompt CACHEADO — mismo para todos los requests
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=tools,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    research_text = ""
    for block in response.content:
        if hasattr(block, "text") and block.text is not None:
            research_text += block.text

    usage = response.usage
    return {
        "topic": topic,
        "page_type": page_type,
        "target_market": target_market,
        "output_language": output_language,
        "research": research_text,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        },
    }
