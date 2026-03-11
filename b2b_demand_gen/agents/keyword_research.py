"""
Agente 1: Keyword Research para B2B Demand Generation.

Usa Claude Opus 4.6 con web_search para investigar:
- Keywords primarias y secundarias de alta intención B2B
- Volumen de búsqueda estimado y competencia
- Pain points del buyer persona
- Preguntas frecuentes (FAQ seeds)
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


def run_keyword_research(service_topic: str, target_market: str = "B2B") -> dict:
    """
    Ejecuta investigación de keywords para el servicio dado.

    Args:
        service_topic: Tema/servicio a investigar (ej: "generación de demanda B2B")
        target_market: Mercado objetivo (default: "B2B")

    Returns:
        dict con la investigación completa de keywords
    """
    client = anthropic.Anthropic()

    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
    ]

    messages = [
        {
            "role": "user",
            "content": f"""Realiza una investigación exhaustiva de keywords para una página de servicios sobre:
**Servicio:** {service_topic}
**Mercado:** {target_market}

Investiga y entrega:

1. **Keywords Primarias** (3-5): Las más relevantes con alta intención de compra
2. **Keywords Secundarias / LSI** (8-10): Variaciones y sinónimos importantes
3. **Long-tail Keywords** (5-8): Frases específicas de 4+ palabras que usan compradores B2B
4. **Preguntas del Buyer** (5-7): Qué preguntas hacen los decision makers en Google
5. **Pain Points Detectados**: Problemas principales que buscan resolver
6. **Ángulos de Contenido**: 3 enfoques diferenciadores para la página

Usa búsquedas web para validar tendencias actuales y competencia.""",
        }
    ]

    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    # Manejar loop de tool use si es necesario
    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                # El servidor maneja web_search automáticamente,
                # pero si retorna tool_use explícito, procesamos
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Búsqueda completada para: {block.input}",
                })

        messages.append({"role": "assistant", "content": response.content})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

    # Extraer texto final
    research_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            research_text += block.text

    return {
        "service_topic": service_topic,
        "target_market": target_market,
        "research": research_text,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
