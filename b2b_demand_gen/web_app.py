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

        emit("step_complete", {
            "step": 2,
            "usage": copy_result["usage"],
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
                    "outputs": [f"{timestamp}_{slug}_keywords.json", f"{timestamp}_{slug}_copy.json"],
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
                "outputs": [f"{timestamp}_{slug}_keywords.json", f"{timestamp}_{slug}_copy.json"],
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
            "outputs": [
                f"{timestamp}_{slug}_keywords.json",
                f"{timestamp}_{slug}_copy.json",
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
    """Lista todos los archivos de output generados."""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    files = sorted(OUTPUTS_DIR.glob("*.json"), reverse=True)
    return [{"name": f.name, "size": f.stat().st_size} for f in files]


@app.get("/api/outputs/{filename}")
async def get_output(filename: str):
    """Retorna el contenido de un archivo de output."""
    filepath = OUTPUTS_DIR / filename
    if not filepath.exists() or filepath.suffix != ".json":
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(content=data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
