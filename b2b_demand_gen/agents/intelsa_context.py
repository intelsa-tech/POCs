"""
Contexto empresarial de Intelsa.co y utilidades de idioma compartidas por todos los agentes.

Este módulo se importa en todos los agentes. El contenido se incluye en los system prompts
que se marcan con cache_control=ephemeral → se cachea en Anthropic (ahorro ~90% en tokens
repetidos dentro de la misma sesión de 5 minutos).
"""

# ─── Perfil de Intelsa — se inyecta en el system prompt (CACHEADO) ────────────
INTELSA_PROFILE = """
SOBRE INTELSA (contexto obligatorio):
- BPO nearshore con sede en Medellín, Colombia, 11+ años de operación
- Certificación ISO 27001 (seguridad de datos)
- Industrias atendidas: ecommerce, salud, tabacaleras, constructoras, logística,
  consumo masivo (clientes Fortune 500)
- Mercados: EE.UU. (inglés) y LATAM (español/portugués)
- Diferenciador: IA + talento humano bilingüe — no solo labor arbitrage

AUDIENCIA OBJETIVO:
- VP of Operations, Head of CX, COO en empresas medianas y enterprise
- Evalúan outsourcing por primera vez o están insatisfechos con proveedor actual
- Sus métricas clave: CSAT, AHT, costo por ticket, tiempo de implementación
- Toman decisiones de $200K–$2M anuales — necesitan credibilidad, no hype

REGLAS DE ESCRITURA (OBLIGATORIAS — NO NEGOCIABLES):
- Directo, basado en valor de negocio, sin jerga innecesaria
- Responder siempre las tres preguntas del comprador:
  ¿por qué Intelsa?, ¿por qué Colombia?, ¿por qué ahora?
- NUNCA inventar estadísticas — si no tienes el dato real,
  usar "nuestros clientes reportan..." o eliminar el dato completamente
- NUNCA usar cada palabra con mayúscula inicial en títulos o encabezados:
  CORRECTO:   "Los mejores BPO nearshore para e-commerce en Latam"
  INCORRECTO: "Los Mejores BPO Nearshore Para E-Commerce En Latam"
  Esta regla aplica para H1, H2, H3, títulos de cards y CTAs
- Tono ejecutivo en páginas de servicio
- Tono más directo y educativo en contenido de blog

CTA STYLE (OBLIGATORIO):
- Específico y de bajo riesgo, nunca agresivo ni con urgencia artificial
- Ejemplos del tono correcto:
  EN: "See if Intelsa is the right fit for your team"
  EN: "Get a custom cost estimate in 48 hours"
  EN: "Talk to someone who's run this operation before"
  EN: "See how we'd staff your operation"
  ES: "Cuéntanos cómo es tu operación hoy"
  ES: "Agenda una llamada de 30 minutos sin compromiso"
- NUNCA usar: "¡Empieza hoy!", "Oferta limitada", "Contáctanos ahora",
  "¡Transforma tu negocio!", ni ninguna frase con signo de exclamación
- El CTA debe responder una pregunta específica del comprador,
  nunca crear presión de tiempo artificial

ESTRUCTURA PARA LLM CITATION (importante para SEO semántico y snippets):
- Cada sección principal debe comenzar con la pregunta que responde
- La definición del servicio va en las primeras 2 oraciones del body
- Los párrafos introductorios deben poder funcionar como respuesta standalone
  si un sistema de IA los extrae del contexto
- FAQ: mínimo 6 preguntas en formato pregunta/respuesta literal
- Respuestas de FAQ: máximo 50 palabras, respuesta directa primero, detalle después

TÍTULOS SEGÚN TIPO DE PÁGINA:
- Páginas de servicio: específicos y orientados al comprador
  CORRECTO:   "Customer support outsourcing to Colombia: costs, timeline, and what to expect"
  INCORRECTO: "10 powerful reasons to outsource your contact center now"
- Blog educativo: directos y basados en valor real
  CORRECTO:   "The real cost of outsourcing customer support to Colombia vs. Philippines (2025)"
  INCORRECTO: "Why outsourcing is the best decision you'll ever make"
- Nunca usar clickbait, listas numéricas vacías ni promesas exageradas
"""

# ─── Idiomas soportados ────────────────────────────────────────────────────────
LANGUAGE_LABELS: dict[str, str] = {
    "es": "español",
    "en": "English",
    "pt": "português (Brasil)",
    "fr": "français",
    "de": "Deutsch",
}

# Mercados por idioma (usado en el UI y en hints al modelo)
LANGUAGE_MARKETS: dict[str, str] = {
    "es": "LATAM / Colombia / México",
    "en": "United States / English-speaking markets",
    "pt": "Brasil",
    "fr": "Francia / mercados francófonos",
    "de": "Alemania / mercados germanófonos",
}


def get_language_instruction(output_language: str) -> str:
    """
    Retorna la instrucción de idioma de salida para el bloque DINÁMICO del prompt.
    Si el idioma es español (default) retorna string vacío para no desperdiciar tokens.
    """
    if output_language not in LANGUAGE_LABELS or output_language == "es":
        return ""
    label = LANGUAGE_LABELS[output_language]
    market = LANGUAGE_MARKETS.get(output_language, label)
    return (
        f"\n\n**OUTPUT LANGUAGE / IDIOMA DE SALIDA:**\n"
        f"Generate ALL output content in {label} (target market: {market}).\n"
        f"Every JSON field — h1, meta_description, hero_subtitle, section bodies, "
        f"FAQ answers, CTAs — must be written entirely in {label}.\n"
        f"Adapt cultural references, examples, and tone for the {market} market."
    )
