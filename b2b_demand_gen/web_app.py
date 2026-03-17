"""
Web UI para el pipeline B2B Demand Generation — Intelsa.co

Corre con:
    cd b2b_demand_gen
    uvicorn web_app:app --reload --port 8000
"""

import asyncio
import functools
import json
import os
import queue
import sys
import threading
import uuid
from datetime import datetime
from html import escape as _esc
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

# Asegurar que los imports del proyecto funcionen correctamente
_BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(_BASE_DIR))
load_dotenv(_BASE_DIR / ".env")

from agents.copy_blog import run_copy_blog
from agents.copy_industries import run_copy_industries
from agents.copy_services import run_copy_services
from agents.keyword_research import run_keyword_research
from agents.webflow_uploader import run_webflow_upload
from agents.intelsa_context import LANGUAGE_LABELS
import db as database

OUTPUTS_DIR = _BASE_DIR / "outputs"
TEMPLATES_DIR = _BASE_DIR / "templates"

COPY_AGENTS = {
    "service": run_copy_services,
    "industry": run_copy_industries,
    "blog": run_copy_blog,
}

# ─── Estado en memoria de los jobs ───────────────────────────────────────────
_jobs: dict[str, dict] = {}

app = FastAPI(title="B2B Content Generator — Intelsa")

# Inicializar la DB al arrancar
database.init_db()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _save_output(data: dict, filename: str) -> str:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(filepath)


def _sum_cache(usage: dict) -> tuple[int, int]:
    """Extrae (cache_read, cache_creation) de un dict de usage."""
    return (
        usage.get("cache_read_input_tokens", 0) or 0,
        usage.get("cache_creation_input_tokens", 0) or 0,
    )


def _generate_html_preview(
    copy_data: dict,
    keyword_research_text: str,
    page_type: str,
    topic: str,
    output_language: str,
) -> str:
    """Genera un HTML standalone con el contenido generado, listo para revisar antes de Webflow."""
    meta_title = _esc(copy_data.get("meta_title", topic))
    meta_description = _esc(copy_data.get("meta_description", ""))
    h1 = _esc(copy_data.get("h1", topic))
    hero_subtitle = _esc(copy_data.get("hero_subtitle", ""))
    cta_primary = _esc(copy_data.get("cta_primary", "Contáctanos"))
    cta_final = _esc(copy_data.get("cta_final", ""))
    sections = copy_data.get("sections", [])
    faq = copy_data.get("faq", [])

    # Blog-specific fields
    intro_paragraph = copy_data.get("intro_paragraph", "")
    takeaways = copy_data.get("takeaways", [])
    internal_cta_title = copy_data.get("internal_cta_title", "")
    internal_cta_body = copy_data.get("internal_cta_body", "")
    internal_cta_button = copy_data.get("internal_cta_button", "")
    conclusion_body = copy_data.get("conclusion_body", "")
    focus_keyword = copy_data.get("focus_keyword", "")
    secondary_keywords = copy_data.get("secondary_keywords", [])
    reading_time = copy_data.get("reading_time", "")
    category = copy_data.get("category", "")
    tags = copy_data.get("tags", [])

    def nl2br(s: str) -> str:
        return _esc(s).replace("\n", "<br>")

    # Sections HTML
    sections_html = ""
    for sec in sections:
        h2_text = _esc(sec.get("h2", ""))
        body_text = nl2br(sec.get("body", ""))
        h3_html = ""
        for item in sec.get("h3_items", []):
            h3t = _esc(item.get("h3", ""))
            h3b = nl2br(item.get("body", ""))
            if h3t:
                h3_html += f"<h3>{h3t}</h3><p>{h3b}</p>"
        ki = sec.get("key_insight", "")
        insight_html = f'<blockquote class="insight">{_esc(ki)}</blockquote>' if ki else ""
        sections_html += f"""
      <section class="content-section">
        <h2>{h2_text}</h2>
        <p>{body_text}</p>
        {h3_html}
        {insight_html}
      </section>"""

    # FAQ HTML
    faq_html = ""
    for item in faq:
        q = _esc(item.get("question", ""))
        a = nl2br(item.get("answer", ""))
        faq_html += f"""
      <div class="faq-item">
        <strong class="question">{q}</strong>
        <p class="answer">{a}</p>
      </div>"""

    # Blog extras
    intro_html = f'<p class="intro-paragraph">{nl2br(intro_paragraph)}</p>' if intro_paragraph else ""
    takeaways_html = ""
    if takeaways:
        items = "".join(f"<li>{_esc(t)}</li>" for t in takeaways)
        takeaways_html = f'<div class="takeaways"><h3>Puntos clave</h3><ul>{items}</ul></div>'
    internal_cta_html = ""
    if internal_cta_title:
        internal_cta_html = f"""
      <div class="internal-cta">
        <h3>{_esc(internal_cta_title)}</h3>
        <p>{nl2br(internal_cta_body)}</p>
        <span class="cta-btn">{_esc(internal_cta_button)}</span>
      </div>"""
    conclusion_html = f'<div class="conclusion"><p>{nl2br(conclusion_body)}</p></div>' if conclusion_body else ""

    # Keywords / tags badges
    kw_badges = ""
    if focus_keyword:
        kw_badges += f'<span class="badge">&#127919; {_esc(focus_keyword)}</span>'
    for kw in secondary_keywords[:5]:
        kw_badges += f'<span class="badge secondary">{_esc(kw)}</span>'
    tags_html = "".join(f'<span class="tag">{_esc(t)}</span>' for t in tags)

    kw_research_html = ""
    if keyword_research_text:
        kw_research_html = f"""
    <details class="kw-research">
      <summary>&#128202; Keyword Research completo</summary>
      <pre class="kw-content">{_esc(keyword_research_text)}</pre>
    </details>"""

    pt_label = {"service": "Página de Servicios", "industry": "Página de Industria", "blog": "Artículo de Blog"}.get(page_type, page_type)
    cat_span = f'<span class="label">Categoría:</span><span>{_esc(category)}</span>' if category else ""
    rt_span = f'<span class="label">Lectura:</span><span>{_esc(reading_time)}</span>' if reading_time else ""
    kw_section = f'<div class="keywords-badges" style="margin-top:12px;">{kw_badges}</div>' if kw_badges else ""
    tags_section = f'<div class="tags">{tags_html}</div>' if tags_html else ""
    faq_section = f'<section class="faq-section"><h2>Preguntas frecuentes</h2>{faq_html}</section>' if faq_html else ""
    cta_final_section = f'<div class="cta-final-section"><span class="cta-btn">{cta_final}</span></div>' if cta_final else ""

    return f"""<!DOCTYPE html>
<html lang="{output_language}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta_title}</title>
  <meta name="description" content="{meta_description}">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1e293b;line-height:1.7;background:#f8fafc}}
    .meta-bar{{background:#1e293b;color:#94a3b8;padding:8px 24px;font-size:12px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}}
    .meta-bar strong{{color:#fff}}.meta-bar .label{{color:#64748b;margin-left:8px}}
    .container{{max-width:860px;margin:0 auto;padding:0 24px 80px}}
    .hero{{background:linear-gradient(135deg,#1e40af 0%,#3730a3 100%);color:#fff;padding:64px 24px;text-align:center}}
    .hero h1{{font-size:clamp(22px,4vw,40px);font-weight:800;line-height:1.2;max-width:800px;margin:0 auto 16px}}
    .hero .subtitle{{font-size:18px;opacity:.85;max-width:640px;margin:0 auto 32px}}
    .cta-btn{{display:inline-block;background:#f97316;color:#fff;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;cursor:pointer;text-decoration:none}}
    .intro-paragraph{{font-size:17px;color:#334155;border-left:4px solid #3b82f6;padding-left:16px;margin:32px 0;font-style:italic}}
    .keywords-badges{{display:flex;flex-wrap:wrap;gap:8px}}
    .badge{{background:#dbeafe;color:#1d4ed8;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600}}
    .badge.secondary{{background:#e0f2fe;color:#0369a1}}
    .meta-info{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin:24px 0}}
    .meta-info h4{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-bottom:8px}}
    .meta-title-text{{font-weight:700;color:#1e293b;font-size:15px}}
    .meta-desc-text{{color:#64748b;font-size:13px;margin-top:6px}}
    .tags{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}
    .tag{{background:#f1f5f9;color:#475569;padding:3px 10px;border-radius:20px;font-size:11px}}
    .content-section{{background:#fff;border-radius:12px;padding:32px;margin:16px 0;border:1px solid #e2e8f0}}
    .content-section h2{{font-size:22px;font-weight:700;color:#1e293b;margin-bottom:14px;padding-bottom:12px;border-bottom:2px solid #f1f5f9}}
    .content-section h3{{font-size:17px;font-weight:600;color:#3730a3;margin:20px 0 8px}}
    .content-section p{{color:#475569;margin-bottom:10px}}
    .insight{{border-left:4px solid #f97316;padding:12px 16px;background:#fff7ed;color:#9a3412;font-style:italic;margin:16px 0;border-radius:0 8px 8px 0}}
    .faq-section{{background:#f8fafc;border-radius:12px;padding:32px;margin:16px 0;border:1px solid #e2e8f0}}
    .faq-section h2{{font-size:20px;font-weight:700;margin-bottom:20px}}
    .faq-item{{background:#fff;border-radius:8px;padding:16px;margin-bottom:10px;border:1px solid #e2e8f0}}
    .question{{display:block;color:#1e293b;font-size:15px;margin-bottom:6px}}
    .answer{{color:#64748b;font-size:13px;margin:0}}
    .takeaways{{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:24px;margin:16px 0}}
    .takeaways h3{{color:#166534;margin-bottom:10px}}
    .takeaways ul{{list-style:none;padding:0}}
    .takeaways li{{padding:5px 0 5px 22px;position:relative;color:#15803d}}
    .takeaways li::before{{content:'✓';position:absolute;left:0;font-weight:700}}
    .internal-cta{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:28px;margin:24px 0;text-align:center}}
    .internal-cta h3{{color:#1e40af;font-size:19px;margin-bottom:10px}}
    .internal-cta p{{color:#3730a3;margin-bottom:18px}}
    .conclusion{{background:#fefce8;border:1px solid #fde68a;border-radius:12px;padding:24px;margin:16px 0}}
    .conclusion p{{color:#78350f}}
    .cta-final-section{{text-align:center;padding:48px 0}}
    .cta-final-section .cta-btn{{font-size:18px;padding:18px 44px}}
    .kw-research{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin:32px 0;overflow:hidden}}
    .kw-research summary{{padding:14px 20px;font-weight:600;color:#374151;cursor:pointer;font-size:13px;user-select:none}}
    .kw-research summary:hover{{background:#f8fafc}}
    .kw-content{{padding:20px;font-size:11px;font-family:'Courier New',monospace;white-space:pre-wrap;color:#374151;max-height:500px;overflow-y:auto;background:#f8fafc;border-top:1px solid #e2e8f0}}
    .generated-notice{{text-align:center;padding:20px;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;margin-top:40px}}
    hr{{border:none;border-top:1px solid #e2e8f0;margin:24px 0}}
  </style>
</head>
<body>

<div class="meta-bar">
  <strong>Intelsa B2B Content Generator</strong>
  <span class="label">Tipo:</span><span>{pt_label}</span>
  <span class="label">Idioma:</span><span>{output_language.upper()}</span>
  {cat_span}
  {rt_span}
</div>

<div class="hero">
  <h1>{h1}</h1>
  {"<p class='subtitle'>" + hero_subtitle + "</p>" if hero_subtitle else ""}
  <span class="cta-btn">{cta_primary}</span>
</div>

<div class="container">
  <div class="meta-info">
    <h4>SEO Meta</h4>
    <p class="meta-title-text">{meta_title}</p>
    <p class="meta-desc-text">{meta_description}</p>
    {kw_section}
    {tags_section}
  </div>

  {intro_html}
  {sections_html}
  {takeaways_html}
  {internal_cta_html}
  {conclusion_html}
  {faq_section}
  {cta_final_section}
  {kw_research_html}

  <div class="generated-notice">
    Generado por Intelsa B2B Content Generator &mdash; preview previo a publicación en Webflow
  </div>
</div>

</body>
</html>"""


def _run_pipeline(job_id: str, params: dict):
    """Pipeline completo corriendo en un thread de fondo."""
    q = _jobs[job_id]["queue"]

    def emit(event_type: str, data: dict):
        q.put({"type": event_type, "data": data})

    try:
        topic = params["topic"]
        page_type = params.get("page_type", "service")
        target_market = params.get("target_market", "empresas B2B medianas y grandes")
        company_context = params.get("company_context", "")
        output_language = params.get("output_language", "es")
        pt_upper = page_type.upper()
        site_id = params.get("site_id") or os.environ.get("WEBFLOW_SITE_ID")
        collection_id = (
            params.get("collection_id")
            or os.environ.get(f"WEBFLOW_COLLECTION_ID_{pt_upper}")
            or os.environ.get("WEBFLOW_COLLECTION_ID")
        ) or None
        template_item_id = (
            params.get("template_item_id")
            or os.environ.get(f"WEBFLOW_TEMPLATE_ITEM_ID_{pt_upper}")
            or os.environ.get("WEBFLOW_TEMPLATE_ITEM_ID")
        ) or None
        auto_publish = params.get("auto_publish", False)
        skip_upload = params.get("skip_upload", False)
        skip_review = params.get("skip_review", False)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = topic.lower().replace(" ", "_")[:30]

        # ── PASO 1: Keyword Research ──────────────────────────────────────────
        emit("step_start", {"step": 1, "name": "Keyword Research"})

        keyword_result = run_keyword_research(
            topic, target_market, page_type=page_type, output_language=output_language
        )
        _save_output(keyword_result, f"{timestamp}_{slug}_keywords.json")

        emit("step_complete", {
            "step": 1,
            "preview": keyword_result["research"],
            "usage": keyword_result["usage"],
        })

        # ── PASO 2: Copy ──────────────────────────────────────────────────────
        emit("step_start", {"step": 2, "name": f"Copywriting — {page_type}"})

        copy_fn = COPY_AGENTS[page_type]
        copy_result = copy_fn(keyword_result, company_context, output_language)
        _save_output(copy_result, f"{timestamp}_{slug}_copy.json")

        # Generar HTML preview y guardarlo en outputs/
        html_filename = f"{timestamp}_{slug}_preview.html"
        html_content = _generate_html_preview(
            copy_result.get("copy_data", {}),
            keyword_result.get("research", ""),
            page_type,
            topic,
            output_language,
        )
        OUTPUTS_DIR.mkdir(exist_ok=True)
        (OUTPUTS_DIR / html_filename).write_text(html_content, encoding="utf-8")

        emit("step_complete", {
            "step": 2,
            "usage": copy_result["usage"],
            "html_file": html_filename,
        })

        # ── REVISIÓN HUMANA ───────────────────────────────────────────────────
        if not skip_upload and not skip_review:
            emit("review_needed", {
                "copy_data": copy_result.get("copy_data", {}),
                "page_type": copy_result.get("page_type", "service"),
                "topic": copy_result.get("topic", topic),
            })
            _jobs[job_id]["review_event"].wait()
            approved = _jobs[job_id]["review_approved"]

            if not approved:
                # Guardar en DB aunque sea rechazado (para tracking de créditos)
                k_read, k_cre = _sum_cache(keyword_result["usage"])
                c_read, c_cre = _sum_cache(copy_result["usage"])
                database.save_generation(
                    topic=topic, page_type=page_type, target_market=target_market,
                    output_language=output_language, company_context=company_context,
                    complete_file=f"{timestamp}_{slug}_copy.json",
                    keyword_tokens=keyword_result["usage"]["input_tokens"] + keyword_result["usage"]["output_tokens"],
                    copy_tokens=copy_result["usage"]["input_tokens"] + copy_result["usage"]["output_tokens"],
                    webflow_tokens=0,
                    cache_read_tokens=k_read + c_read,
                    cache_creation_tokens=k_cre + c_cre,
                    status="rejected",
                )
                emit("pipeline_complete", {
                    "status": "rejected",
                    "message": "Copy rechazado. Pipeline detenido.",
                    "keyword_research": keyword_result.get("research", ""),
                    "copy_data": copy_result.get("copy_data", {}),
                    "page_type": page_type,
                    "html_file": html_filename,
                    "outputs": [f"{timestamp}_{slug}_keywords.json", f"{timestamp}_{slug}_copy.json", html_filename],
                })
                return

            emit("review_approved", {"message": "Copy aprobado. Continuando con el upload…"})

        # ── PASO 3: Webflow Upload ────────────────────────────────────────────
        if skip_upload:
            k_read, k_cre = _sum_cache(keyword_result["usage"])
            c_read, c_cre = _sum_cache(copy_result["usage"])
            database.save_generation(
                topic=topic, page_type=page_type, target_market=target_market,
                output_language=output_language, company_context=company_context,
                complete_file=f"{timestamp}_{slug}_copy.json",
                keyword_tokens=keyword_result["usage"]["input_tokens"] + keyword_result["usage"]["output_tokens"],
                copy_tokens=copy_result["usage"]["input_tokens"] + copy_result["usage"]["output_tokens"],
                webflow_tokens=0,
                cache_read_tokens=k_read + c_read,
                cache_creation_tokens=k_cre + c_cre,
                status="draft",
            )
            emit("pipeline_complete", {
                "status": "completed_no_upload",
                "message": "Pipeline completado. Upload a Webflow omitido (skip-upload).",
                "keyword_research": keyword_result.get("research", ""),
                "copy_data": copy_result.get("copy_data", {}),
                "page_type": page_type,
                "html_file": html_filename,
                "outputs": [f"{timestamp}_{slug}_keywords.json", f"{timestamp}_{slug}_copy.json", html_filename],
            })
            return

        emit("step_start", {"step": 3, "name": "Webflow Upload"})

        webflow_result = run_webflow_upload(
            copy_result,
            site_id=site_id,
            collection_id=collection_id,
            template_item_id=template_item_id,
            auto_publish=auto_publish,
        )
        _save_output(webflow_result, f"{timestamp}_{slug}_webflow.json")

        emit("step_complete", {
            "step": 3,
            "result_preview": webflow_result["result"],
            "usage": webflow_result["usage"],
        })

        total = {
            "keyword_research": keyword_result,
            "copywriting": copy_result,
            "webflow": webflow_result,
        }
        complete_file = f"{timestamp}_{slug}_COMPLETE.json"
        _save_output(total, complete_file)

        # ── Guardar en DB ─────────────────────────────────────────────────────
        k_read, k_cre = _sum_cache(keyword_result["usage"])
        c_read, c_cre = _sum_cache(copy_result["usage"])
        w_read, w_cre = _sum_cache(webflow_result["usage"])
        database.save_generation(
            topic=topic, page_type=page_type, target_market=target_market,
            output_language=output_language, company_context=company_context,
            complete_file=complete_file,
            keyword_tokens=keyword_result["usage"]["input_tokens"] + keyword_result["usage"]["output_tokens"],
            copy_tokens=copy_result["usage"]["input_tokens"] + copy_result["usage"]["output_tokens"],
            webflow_tokens=webflow_result["usage"]["input_tokens"] + webflow_result["usage"]["output_tokens"],
            cache_read_tokens=k_read + c_read + w_read,
            cache_creation_tokens=k_cre + c_cre + w_cre,
            status="published" if auto_publish else "draft",
        )

        emit("pipeline_complete", {
            "status": "completed",
            "message": "✅ Pipeline completado exitosamente.",
            "webflow_preview": webflow_result["result"],
            "keyword_research": keyword_result.get("research", ""),
            "copy_data": copy_result.get("copy_data", {}),
            "page_type": page_type,
            "output_language": output_language,
            "html_file": html_filename,
            "outputs": [
                f"{timestamp}_{slug}_keywords.json",
                f"{timestamp}_{slug}_copy.json",
                html_filename,
                f"{timestamp}_{slug}_webflow.json",
                complete_file,
            ],
        })

    except Exception as exc:
        emit("pipeline_error", {"message": str(exc)})
    finally:
        q.put(None)


# ─── Rutas ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/jobs")
async def create_job(request: Request):
    """Inicia un nuevo job de pipeline y retorna su ID."""
    params = await request.json()

    if not params.get("topic", "").strip():
        raise HTTPException(status_code=400, detail="El campo 'topic' es requerido.")

    if params.get("page_type", "service") not in COPY_AGENTS:
        raise HTTPException(status_code=400, detail="page_type inválido.")

    if params.get("output_language", "es") not in LANGUAGE_LABELS:
        raise HTTPException(status_code=400, detail="output_language inválido.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "queue": queue.Queue(),
        "review_event": threading.Event(),
        "review_approved": False,
        "status": "running",
    }

    thread = threading.Thread(target=_run_pipeline, args=(job_id, params), daemon=True)
    thread.start()

    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE stream de eventos del pipeline."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    async def event_generator():
        while True:
            try:
                event = _jobs[job_id]["queue"].get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.15)
                yield ": heartbeat\n\n"
                continue

            if event is None:
                yield "event: done\ndata: {}\n\n"
                break

            payload = json.dumps(event["data"], ensure_ascii=False)
            yield f"event: {event['type']}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/jobs/{job_id}/review")
async def submit_review(job_id: str, request: Request):
    """Recibe la decisión de revisión humana."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    body = await request.json()
    approved = bool(body.get("approved", False))

    _jobs[job_id]["review_approved"] = approved
    _jobs[job_id]["review_event"].set()

    return {"status": "ok", "approved": approved}


# ─── Historial (DB) ───────────────────────────────────────────────────────────

@app.get("/api/history")
async def get_history(
    limit: int = 50,
    page_type: str | None = None,
    status: str | None = None,
    language: str | None = None,
):
    """Lista el historial de generaciones con filtros opcionales."""
    return database.list_generations(
        limit=limit, page_type=page_type, status=status, language=language
    )


@app.get("/api/history/stats")
async def get_stats():
    """Estadísticas de uso: tokens, cache, generaciones por tipo."""
    return database.get_stats()


@app.patch("/api/history/{gen_id}/status")
async def update_gen_status(gen_id: int, request: Request):
    """Actualiza el status de una generación (draft → approved → published)."""
    body = await request.json()
    new_status = body.get("status")
    if new_status not in ("draft", "approved", "published", "rejected"):
        raise HTTPException(status_code=400, detail="Status inválido.")
    database.update_status(
        gen_id,
        status=new_status,
        webflow_item_id=body.get("webflow_item_id"),
        webflow_url=body.get("webflow_url"),
    )
    return {"status": "ok"}


# ─── Webflow Upload retroactivo ───────────────────────────────────────────────

@app.post("/api/history/{gen_id}/webflow-upload")
async def upload_history_to_webflow(gen_id: int, request: Request):
    """
    Sube a Webflow un ítem del historial que no fue subido anteriormente
    (ej. generaciones con skip_upload=True o que fallaron en el paso 3).
    """
    gen = database.get_generation(gen_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generación no encontrada.")
    if not gen.get("complete_file"):
        raise HTTPException(status_code=400, detail="No hay archivo de output para esta generación.")

    filepath = OUTPUTS_DIR / gen["complete_file"]
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Archivo de output no encontrado: {gen['complete_file']}")

    body = await request.json()
    page_type = gen.get("page_type", "service")
    pt_upper = page_type.upper()
    site_id = body.get("site_id") or os.environ.get("WEBFLOW_SITE_ID")
    collection_id = (
        body.get("collection_id")
        or os.environ.get(f"WEBFLOW_COLLECTION_ID_{pt_upper}")
        or os.environ.get("WEBFLOW_COLLECTION_ID")
    ) or None
    template_item_id = (
        body.get("template_item_id")
        or os.environ.get(f"WEBFLOW_TEMPLATE_ITEM_ID_{pt_upper}")
        or os.environ.get("WEBFLOW_TEMPLATE_ITEM_ID")
    ) or None
    auto_publish = body.get("auto_publish", False)

    # Cargar datos del archivo de output
    with open(filepath, "r", encoding="utf-8") as f:
        file_data = json.load(f)

    # El archivo puede ser _COMPLETE.json (tiene key "copywriting") o _copy.json (directo)
    copy_result = file_data.get("copywriting", file_data)

    # Ejecutar en un thread para no bloquear el event loop
    webflow_result = await asyncio.get_event_loop().run_in_executor(
        None,
        functools.partial(
            run_webflow_upload,
            copy_result,
            site_id=site_id,
            collection_id=collection_id,
            template_item_id=template_item_id,
            auto_publish=auto_publish,
        ),
    )

    # Guardar el resultado del upload
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = gen["topic"].lower().replace(" ", "_")[:30]
    _save_output(webflow_result, f"{timestamp}_{slug}_webflow.json")

    # Actualizar status en DB
    new_status = "published" if auto_publish else "draft"
    database.update_status(gen_id, status=new_status)

    return {
        "status": "ok",
        "webflow_result": webflow_result.get("result", ""),
        "iterations": webflow_result.get("iterations", 0),
        "usage": webflow_result.get("usage", {}),
    }


# ─── Outputs (archivos JSON) ──────────────────────────────────────────────────

@app.get("/api/outputs")
async def list_outputs():
    """Lista todos los archivos de output generados (JSON y HTML)."""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    files = sorted(
        [f for f in OUTPUTS_DIR.iterdir() if f.suffix in (".json", ".html")],
        reverse=True,
    )
    return [{"name": f.name, "size": f.stat().st_size} for f in files]


@app.get("/api/outputs/{filename}")
async def get_output(filename: str):
    """Retorna el contenido de un archivo de output (JSON o HTML)."""
    filepath = OUTPUTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    if filepath.suffix == ".html":
        return HTMLResponse(filepath.read_text(encoding="utf-8"))
    if filepath.suffix != ".json":
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(content=data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
