"""
LinkedIn Keyword Researcher - Main
====================================
Punto de entrada. Soporta:

  Modo único:
    python main.py

  Modo programado (loop):
    python main.py --schedule 60          # cada 60 minutos
    python main.py --schedule 120 --headless

  Filtrar keywords manualmente:
    python main.py --keywords "hiring" "staffing" "BPO"

  Ver resultados guardados:
    python main.py --report
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

from config import ALL_KEYWORDS, DEFAULT_CONFIG, ScraperConfig
from notifier import notify
from scraper import LinkedInScraper
from storage import ResultStorage

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join("results", "researcher.log"),
            encoding="utf-8",
            delay=True,      # crea el archivo solo cuando hay algo que escribir
        ),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

async def run_once(config: ScraperConfig, keywords: List[str]):
    """Ejecuta una sola pasada de búsqueda."""
    storage = ResultStorage(config)
    scraper = LinkedInScraper(config)

    logger.info("=" * 60)
    logger.info(f"LinkedIn Keyword Researcher  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Keywords a buscar: {len(keywords)}")
    logger.info(f"Tipos de búsqueda: {config.search_types}")
    logger.info("=" * 60)

    try:
        await scraper.start()
        all_leads = await scraper.run(keywords=keywords)
    finally:
        await scraper.close()

    new_count = storage.save_leads(all_leads)
    notify(all_leads[:new_count] if new_count else [], storage.total_saved())

    logger.info(f"Ejecución completada. Nuevos: {new_count} | Total: {storage.total_saved()}")
    return new_count


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(config: ScraperConfig):
    """Imprime un resumen de todos los leads guardados."""
    storage = ResultStorage(config)
    leads = storage.load_all_leads()

    if not leads:
        print("No hay leads guardados aún. Ejecuta el researcher primero.")
        return

    from collections import Counter
    by_group  = Counter(l["keyword_group"] for l in leads)
    by_type   = Counter(l["search_type"] for l in leads)
    by_kw     = Counter(l["keyword"] for l in leads)

    print(f"\n{'='*60}")
    print(f"  REPORTE DE LEADS  |  Total: {len(leads)}")
    print(f"{'='*60}")

    print("\n📊 Por categoría:")
    for group, count in by_group.most_common():
        print(f"  {group:<40} {count:>4}")

    print("\n🔎 Por tipo de búsqueda:")
    for stype, count in by_type.most_common():
        print(f"  {stype:<20} {count:>4}")

    print("\n🔑 Top keywords:")
    for kw, count in by_kw.most_common(15):
        print(f"  {kw:<40} {count:>4}")

    print(f"\n📁 CSV: {os.path.abspath(os.path.join(config.output_dir, config.output_file))}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="LinkedIn Keyword Researcher – monitorea LinkedIn para detectar oportunidades de negocio"
    )
    parser.add_argument(
        "--keywords", nargs="+", default=None,
        help="Keywords específicas a buscar (por defecto usa config.py)"
    )
    parser.add_argument(
        "--schedule", type=int, default=None, metavar="MINUTOS",
        help="Ejecutar en loop cada N minutos"
    )
    parser.add_argument(
        "--search-types", nargs="+",
        default=["posts", "people"],
        choices=["posts", "people", "companies", "jobs"],
        help="Tipos de búsqueda a realizar"
    )
    parser.add_argument(
        "--max-results", type=int, default=30,
        help="Máximo de resultados por keyword (default: 30)"
    )
    parser.add_argument(
        "--headless", action="store_true", default=True,
        help="Ejecutar browser en modo headless (default: True)"
    )
    parser.add_argument(
        "--no-headless", dest="headless", action="store_false",
        help="Mostrar el browser en pantalla"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Mostrar reporte de leads guardados y salir"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    config = ScraperConfig(
        headless=args.headless,
        search_types=args.search_types,
        max_results_per_keyword=args.max_results,
    )

    # Asegurar que la carpeta de resultados existe
    os.makedirs(config.output_dir, exist_ok=True)

    if args.report:
        print_report(config)
        return

    keywords = args.keywords or ALL_KEYWORDS

    if args.schedule:
        interval_s = args.schedule * 60
        logger.info(f"Modo programado: ejecutando cada {args.schedule} minutos.")
        run_number = 0
        while True:
            run_number += 1
            logger.info(f"\n--- Ejecución #{run_number} ---")
            try:
                asyncio.run(run_once(config, keywords))
            except KeyboardInterrupt:
                logger.info("Detenido por el usuario.")
                break
            except Exception as e:
                logger.error(f"Error en ejecución #{run_number}: {e}", exc_info=True)

            logger.info(f"Próxima ejecución en {args.schedule} minutos...")
            try:
                time.sleep(interval_s)
            except KeyboardInterrupt:
                logger.info("Detenido por el usuario.")
                break
    else:
        asyncio.run(run_once(config, keywords))


if __name__ == "__main__":
    main()
