"""
LinkedIn Keyword Researcher - Configuration
==========================================
Centraliza keywords, filtros y ajustes del scraper.
"""

from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Keywords a monitorear
# Agrupa por categoría para facilitar reportes
# ---------------------------------------------------------------------------
KEYWORD_GROUPS = {
    "BPO / Call Center": [
        "call center",
        "callcenter",
        "contact center",
        "BPO",
        "business process outsourcing",
        "centro de llamadas",
        "centro de contacto",
    ],
    "Hiring / Staffing": [
        "hiring",
        "we are hiring",
        "estamos contratando",
        "staffing",
        "recruitment",
        "reclutamiento",
        "talent acquisition",
        "adquisición de talento",
        "headhunting",
        "outsourcing de personal",
        "staff augmentation",
    ],
    "Operaciones / Soporte": [
        "customer support",
        "soporte al cliente",
        "customer service",
        "servicio al cliente",
        "atención al cliente",
        "helpdesk",
        "help desk",
        "remote agents",
        "agentes remotos",
        "virtual agents",
    ],
    "Señales de demanda": [
        "looking for a call center",
        "buscando call center",
        "necesito call center",
        "need a call center",
        "outsource customer service",
        "externalizar servicio",
        "tercerizar servicio",
    ],
}

# Lista plana de todas las keywords (usada para búsquedas)
ALL_KEYWORDS: List[str] = [kw for group in KEYWORD_GROUPS.values() for kw in group]

# ---------------------------------------------------------------------------
# Filtros de relevancia (palabras que DEBEN aparecer para considerar el post)
# Dejar vacío para no filtrar
# ---------------------------------------------------------------------------
RELEVANCE_FILTERS: List[str] = []   # e.g. ["colombia", "latam", "remote"]

# ---------------------------------------------------------------------------
# Configuración general
# ---------------------------------------------------------------------------
@dataclass
class ScraperConfig:
    # Pausa entre búsquedas (segundos) para no ser detectado como bot
    delay_between_searches: float = 4.0
    # Pausa entre scroll de resultados
    delay_scroll: float = 1.5
    # Máximo de resultados por keyword
    max_results_per_keyword: int = 30
    # Tipo de contenido a buscar: "posts", "people", "companies", "jobs"
    search_types: List[str] = field(default_factory=lambda: ["posts", "people"])
    # Headless browser (False = ver el browser en pantalla)
    headless: bool = True
    # Ruta donde guardar resultados
    output_dir: str = "results"
    # Nombre del archivo de resultados
    output_file: str = "leads.csv"
    # Archivo JSON para rastrear resultados ya vistos (evitar duplicados)
    seen_file: str = "seen_ids.json"
    # Tiempo máximo de espera para cargar página (ms)
    page_timeout: int = 30_000


DEFAULT_CONFIG = ScraperConfig()
