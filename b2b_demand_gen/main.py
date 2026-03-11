"""
Orquestador principal: Pipeline de 3 agentes para crear páginas B2B en Webflow.

Pipeline:
  [Agente 1: Keyword Research] → [Agente 2: Copywriting] → [Agente 3: Webflow Upload]

Uso:
  python main.py
  python main.py --topic "ABM Marketing B2B" --market "SaaS empresas medianas"
  python main.py --topic "Inbound Marketing B2B" --site-id "abc123" --collection-id "def456"
  python main.py --topic "Demand Generation" --publish  # auto-publicar
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

from agents.keyword_research import run_keyword_research
from agents.copywriting import run_copywriting
from agents.webflow_uploader import run_webflow_upload


def print_step(step: int, title: str):
    """Imprime un separador de paso."""
    print(f"\n{'='*60}")
    print(f"  PASO {step}: {title}")
    print(f"{'='*60}\n")


def print_summary(label: str, data: dict):
    """Imprime un resumen legible del output de un agente."""
    usage = data.get("usage", {})
    print(f"\n✓ {label} completado")
    print(f"  Tokens: {usage.get('input_tokens', 0)} input / {usage.get('output_tokens', 0)} output")


def save_output(data: dict, filename: str):
    """Guarda el output de un agente en un archivo JSON."""
    outputs_dir = "outputs"
    os.makedirs(outputs_dir, exist_ok=True)
    filepath = os.path.join(outputs_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Guardado en: {filepath}")


def run_pipeline(
    topic: str,
    target_market: str = "B2B empresas medianas y grandes",
    company_context: str = "",
    site_id: str | None = None,
    collection_id: str | None = None,
    auto_publish: bool = False,
    skip_upload: bool = False,
) -> dict:
    """
    Ejecuta el pipeline completo de 3 agentes.

    Args:
        topic: Servicio/tema para el que crear la página
        target_market: Descripción del mercado objetivo
        company_context: Contexto adicional sobre la empresa
        site_id: ID del sitio Webflow (opcional)
        collection_id: ID de la Collection Webflow (opcional)
        auto_publish: Si True, publica automáticamente en Webflow
        skip_upload: Si True, omite el paso de upload a Webflow

    Returns:
        dict con todos los outputs del pipeline
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = topic.lower().replace(" ", "_")[:30]

    print(f"\n🚀 Iniciando pipeline B2B Demand Generation")
    print(f"   Servicio: {topic}")
    print(f"   Mercado: {target_market}")
    print(f"   Timestamp: {timestamp}")

    # ─── AGENTE 1: KEYWORD RESEARCH ────────────────────────────────────────────
    print_step(1, "KEYWORD RESEARCH")
    print(f"Investigando keywords para: {topic}...")
    start = time.time()

    keyword_result = run_keyword_research(topic, target_market)

    elapsed = time.time() - start
    print_summary("Keyword Research", keyword_result)
    print(f"  Tiempo: {elapsed:.1f}s")
    save_output(keyword_result, f"{timestamp}_{slug}_keywords.json")

    # Vista previa del research
    preview = keyword_result["research"][:500] + "..." if len(keyword_result["research"]) > 500 else keyword_result["research"]
    print(f"\n  Preview:\n{preview}\n")

    # ─── AGENTE 2: COPYWRITING ──────────────────────────────────────────────────
    print_step(2, "COPYWRITING")
    print("Generando copy optimizado para conversión B2B...")
    start = time.time()

    copy_result = run_copywriting(keyword_result, company_context)

    elapsed = time.time() - start
    print_summary("Copywriting", copy_result)
    print(f"  Tiempo: {elapsed:.1f}s")
    save_output(copy_result, f"{timestamp}_{slug}_copy.json")

    # Vista previa del copy
    if isinstance(copy_result["copy_data"], dict) and "hero_headline" in copy_result["copy_data"]:
        print(f"\n  Hero Headline: {copy_result['copy_data'].get('hero_headline', 'N/A')}")
        print(f"  Meta Title: {copy_result['copy_data'].get('meta_title', 'N/A')}")

    # ─── AGENTE 3: WEBFLOW UPLOAD ───────────────────────────────────────────────
    if skip_upload:
        print(f"\n⏭️  Upload a Webflow omitido (--skip-upload)")
        return {
            "keyword_research": keyword_result,
            "copywriting": copy_result,
            "webflow": None,
        }

    print_step(3, "WEBFLOW UPLOAD")
    print("Subiendo contenido a Webflow...")
    start = time.time()

    webflow_result = run_webflow_upload(
        copy_result,
        site_id=site_id,
        collection_id=collection_id,
        auto_publish=auto_publish,
    )

    elapsed = time.time() - start
    print_summary("Webflow Upload", webflow_result)
    print(f"  Tiempo: {elapsed:.1f}s")
    save_output(webflow_result, f"{timestamp}_{slug}_webflow.json")

    print(f"\n  Resultado:\n{webflow_result['result'][:800]}\n")

    # ─── RESUMEN FINAL ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  ✅ PIPELINE COMPLETADO")
    print(f"{'='*60}")
    print(f"  Servicio: {topic}")
    print(f"  Outputs guardados en: outputs/")
    if auto_publish:
        print("  Estado en Webflow: PUBLICADO")
    else:
        print("  Estado en Webflow: DRAFT (requiere revisión y publicación manual)")

    total_result = {
        "keyword_research": keyword_result,
        "copywriting": copy_result,
        "webflow": webflow_result,
    }

    save_output(total_result, f"{timestamp}_{slug}_COMPLETE.json")
    return total_result


def main():
    load_dotenv()

    # Verificar variables de entorno requeridas
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY no está configurado")
        print("Copia .env.example a .env y configura tus credenciales")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Pipeline de agentes IA para crear páginas B2B en Webflow"
    )
    parser.add_argument(
        "--topic",
        default="Generación de Demanda B2B",
        help="Servicio/tema para la página (default: 'Generación de Demanda B2B')",
    )
    parser.add_argument(
        "--market",
        default="empresas B2B medianas y grandes (100-5000 empleados)",
        help="Descripción del mercado objetivo",
    )
    parser.add_argument(
        "--context",
        default="",
        help="Contexto adicional sobre la empresa o servicio",
    )
    parser.add_argument(
        "--site-id",
        default=os.environ.get("WEBFLOW_SITE_ID"),
        help="ID del sitio Webflow (o usar WEBFLOW_SITE_ID env var)",
    )
    parser.add_argument(
        "--collection-id",
        default=os.environ.get("WEBFLOW_COLLECTION_ID"),
        help="ID de la Collection Webflow (o usar WEBFLOW_COLLECTION_ID env var)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publicar automáticamente en Webflow (default: crear como draft)",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Omitir el upload a Webflow (solo ejecutar keyword research + copywriting)",
    )

    args = parser.parse_args()

    # Advertir si no hay token de Webflow
    if not args.skip_upload and not os.environ.get("WEBFLOW_API_TOKEN"):
        print("ADVERTENCIA: WEBFLOW_API_TOKEN no está configurado")
        print("El agente de Webflow fallará. Usa --skip-upload para omitir este paso.")
        print()

    run_pipeline(
        topic=args.topic,
        target_market=args.market,
        company_context=args.context,
        site_id=args.site_id,
        collection_id=args.collection_id,
        auto_publish=args.publish,
        skip_upload=args.skip_upload,
    )


if __name__ == "__main__":
    main()
