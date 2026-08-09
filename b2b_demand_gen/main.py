"""
Orquestador principal: Pipeline de agentes IA para crear páginas B2B en Webflow.

Pipeline:
  [Agente 1: Keyword Research]
          ↓
  [Agente 2: Copy — service | industry | blog]
          ↓
  [Revisión Humana] (omitible con --skip-review)
          ↓
  [Agente 3: Webflow Upload] (omitible con --skip-upload)

Uso:
  python main.py                                             # servicio por defecto
  python main.py --topic "ABM Marketing" --page-type service
  python main.py --topic "SaaS" --page-type industry
  python main.py --topic "Cómo generar más leads B2B" --page-type blog
  python main.py --topic "Demand Generation" --publish      # auto-publicar
  python main.py --topic "Demand Generation" --skip-review  # modo automático/CI
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

from agents.keyword_research import run_keyword_research
from agents.copy_services import run_copy_services
from agents.copy_industries import run_copy_industries
from agents.copy_blog import run_copy_blog
from agents.webflow_uploader import run_webflow_upload

# Mapa de page_type → función de copy
_COPY_AGENTS = {
    "service": run_copy_services,
    "industry": run_copy_industries,
    "blog": run_copy_blog,
}

_PAGE_TYPE_LABELS = {
    "service": "Página de Servicios",
    "industry": "Página de Industria",
    "blog": "Artículo de Blog",
}


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


def human_review_copy(copy_result: dict) -> bool:
    """
    Pausa el pipeline para que un humano revise el copy generado.

    Muestra un resumen del contenido y solicita aprobación antes de subir a Webflow.

    Returns:
        True si el usuario aprueba, False si rechaza (aborta el pipeline).
    """
    copy_data = copy_result.get("copy_data", {})
    page_type = copy_result.get("page_type", "service")

    print(f"\n{'='*60}")
    print("  REVISIÓN HUMANA — Aprueba el copy antes de subir a Webflow")
    print(f"  Tipo de página: {_PAGE_TYPE_LABELS.get(page_type, page_type)}")
    print(f"{'='*60}\n")

    if isinstance(copy_data, dict) and "raw_copy" not in copy_data:
        # Campos a mostrar por tipo de página
        fields_by_type = {
            "service": [
                ("meta_title",          "Meta Title"),
                ("meta_description",    "Meta Description"),
                ("hero_headline",       "Hero Headline"),
                ("hero_subheadline",    "Hero Subheadline"),
                ("hero_cta_primary",    "CTA Principal"),
                ("pain_section_title",  "Pain Points (título)"),
                ("value_prop_title",    "Propuesta de Valor (título)"),
                ("services_title",      "Servicios (título)"),
                ("cta_section_title",   "CTA Final (título)"),
            ],
            "industry": [
                ("meta_title",          "Meta Title"),
                ("meta_description",    "Meta Description"),
                ("hero_headline",       "Hero Headline"),
                ("hero_subheadline",    "Hero Subheadline"),
                ("challenges_title",    "Retos de la Industria (título)"),
                ("approach_title",      "Nuestro Enfoque (título)"),
                ("use_cases_title",     "Casos de Uso (título)"),
                ("metrics_title",       "Métricas (título)"),
                ("cta_section_title",   "CTA Final (título)"),
            ],
            "blog": [
                ("meta_title",          "Meta Title"),
                ("meta_description",    "Meta Description"),
                ("post_title",          "Título del Post"),
                ("post_subtitle",       "Subtítulo"),
                ("focus_keyword",       "Keyword Principal"),
                ("reading_time",        "Tiempo de Lectura"),
                ("category",            "Categoría"),
                ("internal_cta_title",  "CTA Interno (título)"),
            ],
        }

        fields = fields_by_type.get(page_type, fields_by_type["service"])
        for key, label in fields:
            value = copy_data.get(key)
            if value:
                print(f"  {label}:")
                print(f"    {value}\n")

        # Secciones/listas adicionales por tipo
        if page_type == "service":
            metrics = copy_data.get("value_metrics", [])
            if metrics:
                print("  Métricas de impacto:")
                for m in metrics:
                    print(f"    • {m}")
                print()
            services = copy_data.get("services", [])
            if services:
                print(f"  Servicios: {len(services)} items")

        elif page_type == "industry":
            use_cases = copy_data.get("use_cases", [])
            if use_cases:
                print(f"  Casos de uso: {len(use_cases)} casos")
            metrics = copy_data.get("industry_metrics", [])
            if metrics:
                print("  Métricas del sector:")
                for m in metrics:
                    print(f"    • {m}")
                print()

        elif page_type == "blog":
            toc = copy_data.get("toc_items", [])
            if toc:
                print("  Tabla de contenidos:")
                for item in toc:
                    print(f"    • {item}")
                print()
            sections = copy_data.get("sections", [])
            if sections:
                print(f"  Secciones generadas: {len(sections)}")

        faqs = copy_data.get("faqs", [])
        if faqs:
            print(f"  FAQs generadas: {len(faqs)} preguntas")
            for faq in faqs[:2]:
                if isinstance(faq, dict):
                    print(f"    Q: {faq.get('question', '')}")
            print()
    else:
        raw = copy_data.get("raw_copy", copy_result.get("raw_response", ""))
        preview = raw[:1000] + "...\n[truncado — ver outputs/ para el texto completo]" if len(raw) > 1000 else raw
        print(preview)

    print(f"\n  El copy completo está guardado en outputs/")
    print(f"\n{'─'*60}")

    while True:
        answer = input("  ¿Apruebas este copy para subir a Webflow? [s/n]: ").strip().lower()
        if answer in ("s", "si", "sí", "y", "yes"):
            print("\n  ✅ Copy aprobado. Continuando con el upload...\n")
            return True
        elif answer in ("n", "no"):
            print("\n  ❌ Copy rechazado. Pipeline detenido.")
            print("  Puedes editar el archivo JSON en outputs/ y hacer el upload manual.")
            return False
        else:
            print("  Responde 's' para aprobar o 'n' para rechazar.")


def run_pipeline(
    topic: str,
    page_type: str = "service",
    target_market: str = "B2B empresas medianas y grandes",
    company_context: str = "",
    site_id: str | None = None,
    collection_id: str | None = None,
    auto_publish: bool = False,
    skip_upload: bool = False,
    skip_review: bool = False,
) -> dict:
    """
    Ejecuta el pipeline completo.

    Args:
        topic: Servicio/industria/tema para el que crear la página
        page_type: Tipo de página — "service" | "industry" | "blog"
        target_market: Descripción del mercado objetivo
        company_context: Contexto adicional sobre la empresa
        site_id: ID del sitio Webflow (opcional)
        collection_id: ID de la Collection Webflow (opcional)
        auto_publish: Si True, publica automáticamente en Webflow
        skip_upload: Si True, omite el paso de upload a Webflow
        skip_review: Si True, omite la revisión humana y sube directamente

    Returns:
        dict con todos los outputs del pipeline
    """
    if page_type not in _COPY_AGENTS:
        print(f"ERROR: page_type '{page_type}' no válido. Usa: {list(_COPY_AGENTS.keys())}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = topic.lower().replace(" ", "_")[:30]
    page_label = _PAGE_TYPE_LABELS.get(page_type, page_type)

    print(f"\n🚀 Iniciando pipeline B2B Demand Generation")
    print(f"   Tipo: {page_label}")
    print(f"   Tema: {topic}")
    print(f"   Mercado: {target_market}")
    print(f"   Timestamp: {timestamp}")

    # ─── AGENTE 1: KEYWORD RESEARCH ────────────────────────────────────────────
    print_step(1, "KEYWORD RESEARCH")
    print(f"Investigando keywords para: {topic} ({page_type})...")
    start = time.time()

    keyword_result = run_keyword_research(topic, target_market, page_type=page_type)

    elapsed = time.time() - start
    print_summary("Keyword Research", keyword_result)
    print(f"  Tiempo: {elapsed:.1f}s")
    save_output(keyword_result, f"{timestamp}_{slug}_keywords.json")

    preview = keyword_result["research"][:500] + "..." if len(keyword_result["research"]) > 500 else keyword_result["research"]
    print(f"\n  Preview:\n{preview}\n")

    # ─── AGENTE 2: COPY (según page_type) ───────────────────────────────────────
    print_step(2, f"COPYWRITING — {page_label.upper()}")
    print(f"Generando copy para {page_label}...")
    start = time.time()

    copy_fn = _COPY_AGENTS[page_type]
    copy_result = copy_fn(keyword_result, company_context)

    elapsed = time.time() - start
    print_summary(f"Copywriting ({page_type})", copy_result)
    print(f"  Tiempo: {elapsed:.1f}s")
    save_output(copy_result, f"{timestamp}_{slug}_copy.json")

    # Vista previa rápida
    copy_data = copy_result.get("copy_data", {})
    if isinstance(copy_data, dict):
        title_key = "post_title" if page_type == "blog" else "hero_headline"
        print(f"\n  Headline/Título: {copy_data.get(title_key, 'N/A')}")
        print(f"  Meta Title: {copy_data.get('meta_title', 'N/A')}")

    # ─── REVISIÓN HUMANA ────────────────────────────────────────────────────────
    if not skip_upload and not skip_review:
        approved = human_review_copy(copy_result)
        if not approved:
            return {
                "keyword_research": keyword_result,
                "copywriting": copy_result,
                "webflow": None,
                "review_status": "rejected",
            }

    # ─── AGENTE 3: WEBFLOW UPLOAD ───────────────────────────────────────────────
    if skip_upload:
        print(f"\n⏭️  Upload a Webflow omitido (--skip-upload)")
        return {
            "keyword_research": keyword_result,
            "copywriting": copy_result,
            "webflow": None,
        }

    print_step(3, "WEBFLOW UPLOAD")
    print(f"Subiendo {page_label} a Webflow...")
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
    print(f"  Tipo: {page_label}")
    print(f"  Tema: {topic}")
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
        help="Tema para la página (default: 'Generación de Demanda B2B')",
    )
    parser.add_argument(
        "--page-type",
        default="service",
        choices=["service", "industry", "blog"],
        help="Tipo de página a generar (default: service)",
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
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Omitir la revisión humana y subir directamente a Webflow (modo automático)",
    )

    args = parser.parse_args()

    if not args.skip_upload and not os.environ.get("WEBFLOW_API_TOKEN"):
        print("ADVERTENCIA: WEBFLOW_API_TOKEN no está configurado")
        print("El agente de Webflow fallará. Usa --skip-upload para omitir este paso.")
        print()

    run_pipeline(
        topic=args.topic,
        page_type=args.page_type,
        target_market=args.market,
        company_context=args.context,
        site_id=args.site_id,
        collection_id=args.collection_id,
        auto_publish=args.publish,
        skip_upload=args.skip_upload,
        skip_review=args.skip_review,
    )


if __name__ == "__main__":
    main()
